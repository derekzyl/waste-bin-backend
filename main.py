import os
from datetime import datetime
from typing import Optional

import numpy as np
import uvicorn
from database import Base, engine, get_db
from energy_api.routes import router as energy_router
from health_monitoring.routes import router as health_router
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from image_classifier import MaterialClassifier
from models import Bin, BinEvent, DetectionLog
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student IoT Multi-Project Backend", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-load material classifier
_classifier_instance = None


def get_classifier():
    global _classifier_instance
    if _classifier_instance is None:
        print("Lazy loading MaterialClassifier...")
        model_path = os.getenv("MODEL_PATH", "models/material_classifier.pkl")
        _classifier_instance = MaterialClassifier(model_path=model_path)
    return _classifier_instance


# Request/Response Models
class BinUpdate(BaseModel):
    bin_organic_id: str
    bin_non_organic_id: str
    organic_weight: Optional[float] = 0.0
    non_organic_weight: Optional[float] = 0.0
    organic_level: Optional[int] = None  # Added level (0-100%)
    non_organic_level: Optional[int] = None  # Added level (0-100%)
    organic_full: bool
    non_organic_full: bool
    timestamp: Optional[int] = None


class BinStatus(BaseModel):
    id: str
    type: str
    weight: float
    level: int
    full: bool
    last_update: Optional[str] = None


# ... (startup event)
@app.on_event("startup")
async def startup_event():
    # Check for database migrations
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            # Check if outdoor_temp_c exists in energy_sensor_readings
            result = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='energy_sensor_readings' AND column_name='outdoor_temp_c'"
                )
            )
            if not result.fetchone():
                print("Migrating DB: Adding outdoor_temp_c column...")
                conn.execute(
                    text(
                        "ALTER TABLE energy_sensor_readings ADD COLUMN outdoor_temp_c FLOAT"
                    )
                )
                conn.commit()
                print("Migration complete.")

            # Check for voltage columns
            for col in ["sensor_1_voltage", "sensor_2_voltage"]:
                result = conn.execute(
                    text(
                        f"SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name='energy_sensor_readings' AND column_name='{col}'"
                    )
                )
                if not result.fetchone():
                    print(f"Migrating DB: Adding {col} column...")
                    conn.execute(
                        text(
                            f"ALTER TABLE energy_sensor_readings ADD COLUMN {col} FLOAT DEFAULT 220.0"
                        )
                    )
                    conn.commit()
    except Exception as e:
        print(f"Startup migration error: {e}")


# ==================== COMMAND QUEUE ====================
# Simple in-memory command queue: bin_id -> List[Command]
pending_commands = {}


class Command(BaseModel):
    command: str
    params: Optional[dict] = {}
    timestamp: Optional[int] = None


@app.post("/api/bins/{bin_id}/command")
async def queue_command(bin_id: str, cmd: Command):
    """
    Queue a command for the bin to execute (e.g., OPEN, CLOSE).
    """
    if bin_id not in pending_commands:
        pending_commands[bin_id] = []

    cmd.timestamp = int(datetime.now().timestamp() * 1000)
    pending_commands[bin_id].append(cmd.dict())
    return {"status": "queued", "command": cmd}


@app.get("/api/bins/{bin_id}/commands")
async def get_commands(bin_id: str):
    """
    Get pending commands for a bin (Poll & Pop).
    """
    if bin_id in pending_commands and pending_commands[bin_id]:
        cmds = pending_commands[bin_id]
        pending_commands[bin_id] = []  # Clear queue after fetching
        return {"commands": cmds}
    return {"commands": []}


# ==================== API ENDPOINTS ====================


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Koyeb or other monitoring services.
    """
    return {"status": "healthy", "service": "smart-waste-bin-backend"}


# Includes
app.include_router(energy_router)
app.include_router(health_router)


@app.get("/")
async def root():
    return {
        "message": "Student IoT Multi-Project Backend",
        "version": "2.1.0",
        "database": "PostgreSQL",
        "projects": {
            "waste_management": {
                "prefix": "/api",
                "endpoints": {
                    "detect": "/api/detect (POST)",
                    "bins": "/api/bins (GET)",
                    "bin_status": "/api/bins/{bin_id} (GET)",
                    "update_bins": "/api/bins/update (POST)",
                },
            },
            "energy_audit": {"prefix": "/energy", "docs": "/energy/docs"},
            "health_monitoring": {"prefix": "/health", "docs": "/health/docs"},
        },
    }


@app.post("/api/detect")
async def detect_material(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    classifier: MaterialClassifier = Depends(get_classifier),
):
    """
    Detect material type from uploaded image (In-Memory Processing).
    """
    try:
        import cv2  # Lazy import

        # Read file into memory
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)

        # Decode image
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Classify
        result = classifier.classify(image)

        # Log detection to database
        new_detection = DetectionLog(
            material=result.get("material", "UNKNOWN"),
            confidence=result.get("confidence", 0.0),
            method=result.get("method", "unknown"),
            bin_id="unknown",
            timestamp=datetime.now(),
            image_path=None,  # Not saving image locally/cloud for now
        )

        db.add(new_detection)
        db.commit()

        return result

    except Exception as e:
        print(f"Error in detection: {e}")
        return {"material": "UNKNOWN", "confidence": 0.0, "error": str(e)}


@app.post("/api/bins/update")
async def update_bins(data: BinUpdate, db: Session = Depends(get_db)):
    """
    Update bin status from ESP32.
    """
    try:
        # Update organic bin
        organic_bin = db.query(Bin).filter(Bin.id == data.bin_organic_id).first()

        # Calculate level/weight if one is missing
        org_weight = data.organic_weight
        org_level = data.organic_level

        if org_level is not None and org_weight == 0:
            # Estimate weight if only level provided (approximate)
            org_weight = (org_level / 100.0) * 10.0
        elif org_weight > 0 and org_level is None:
            org_level = int((org_weight / 10.0) * 100)

        if organic_bin:
            organic_bin.weight = org_weight
            organic_bin.level = org_level if org_level is not None else 0
            organic_bin.full = data.organic_full
            organic_bin.last_update = datetime.now()

            # Log event if bin became full
            if data.organic_full and not organic_bin.full:
                event = BinEvent(bin_id=data.bin_organic_id, event_type="full")
                db.add(event)
        else:
            # Create new bin if it doesn't exist
            organic_bin = Bin(
                id=data.bin_organic_id,
                type="organic",
                weight=org_weight,
                level=org_level if org_level is not None else 0,
                full=data.organic_full,
            )
            db.add(organic_bin)

        # Update non-organic bin
        non_organic_bin = (
            db.query(Bin).filter(Bin.id == data.bin_non_organic_id).first()
        )

        non_org_weight = data.non_organic_weight
        non_org_level = data.non_organic_level

        if non_org_level is not None and non_org_weight == 0:
            non_org_weight = (non_org_level / 100.0) * 10.0
        elif non_org_weight > 0 and non_org_level is None:
            non_org_level = int((non_org_weight / 10.0) * 100)

        if non_organic_bin:
            non_organic_bin.weight = non_org_weight
            non_organic_bin.level = non_org_level if non_org_level is not None else 0
            non_organic_bin.full = data.non_organic_full
            non_organic_bin.last_update = datetime.now()

            # Log event if bin became full
            if data.non_organic_full and not non_organic_bin.full:
                event = BinEvent(bin_id=data.bin_non_organic_id, event_type="full")
                db.add(event)
        else:
            # Create new bin if it doesn't exist
            non_organic_bin = Bin(
                id=data.bin_non_organic_id,
                type="non_organic",
                weight=non_org_weight,
                level=non_org_level if non_org_level is not None else 0,
                full=data.non_organic_full,
            )
            db.add(non_organic_bin)

        db.commit()

        return {"status": "success", "message": "Bins updated successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")


@app.get("/api/bins")
async def get_all_bins(db: Session = Depends(get_db)):
    """
    Get status of all bins.
    """
    bins = db.query(Bin).all()
    return {
        "bins": [bin.to_dict() for bin in bins],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/bins/{bin_id}")
async def get_bin_status(bin_id: str, db: Session = Depends(get_db)):
    """
    Get status of a specific bin.
    """
    bin = db.query(Bin).filter(Bin.id == bin_id).first()
    if not bin:
        raise HTTPException(status_code=404, detail="Bin not found")

    return bin.to_dict()


@app.get("/api/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get overall statistics.
    """
    bins = db.query(Bin).all()
    total_weight = sum(bin.weight for bin in bins)
    full_bins = sum(1 for bin in bins if bin.full)
    avg_level = sum(bin.level for bin in bins) / len(bins) if bins else 0

    # Get recent detections count
    recent_detections = db.query(DetectionLog).count()

    return {
        "total_bins": len(bins),
        "full_bins": full_bins,
        "total_weight": total_weight,
        "average_level": round(avg_level, 2),
        "total_detections": recent_detections,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/bins/{bin_id}/reset")
async def reset_bin(bin_id: str, db: Session = Depends(get_db)):
    """
    Reset bin (for maintenance).
    """
    bin = db.query(Bin).filter(Bin.id == bin_id).first()
    if not bin:
        raise HTTPException(status_code=404, detail="Bin not found")

    bin.weight = 0.0
    bin.level = 0
    bin.full = False
    bin.last_update = datetime.now()

    # Log reset event
    event = BinEvent(bin_id=bin_id, event_type="reset")
    db.add(event)
    db.commit()

    return {"status": "success", "message": f"Bin {bin_id} reset successfully"}


@app.get("/api/events")
async def get_events(limit: int = 50, db: Session = Depends(get_db)):
    """
    Get recent bin events.
    """
    events = db.query(BinEvent).order_by(BinEvent.timestamp.desc()).limit(limit).all()
    return {"events": [event.to_dict() for event in events], "count": len(events)}


@app.get("/api/detections")
async def get_detections(limit: int = 50, db: Session = Depends(get_db)):
    """
    Get recent material detections.
    """
    detections = (
        db
        .query(DetectionLog)
        .order_by(DetectionLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {
        "detections": [detection.to_dict() for detection in detections],
        "count": len(detections),
    }


@app.post("/api/bins/{bin_id}/event")
async def log_bin_event(bin_id: str, event_type: str, db: Session = Depends(get_db)):
    """
    Log a bin event (open, close, etc.).
    """
    event = BinEvent(bin_id=bin_id, event_type=event_type)
    db.add(event)
    db.commit()

    return {"status": "success", "event": event.to_dict()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
