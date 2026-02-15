import json
import os
from datetime import datetime
from typing import Optional

import numpy as np
import uvicorn

# Import burglary alert models to ensure tables are created
from burglary_alert.models import Alert as BurglaryAlert  # noqa: F401
from burglary_alert.models import Image as BurglaryImage  # noqa: F401
from burglary_alert.models import SystemConfig, TelegramConfig  # noqa: F401

# Burglary Alert System imports
from burglary_alert.routers import (
    alerts_router,
    auth_router,
    devices_router,
    images_router,
    telegram_router,
)
from burglary_alert.routers.alerts import (
    SystemStatusResponse,
    get_system_status,
)
from database import Base, engine, get_db
from energy_api.routes import router as energy_router
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from health_monitoring.routes import router as health_router
from image_classifier import MaterialClassifier
from models import Bin, BinEvent, CommandQueue, DetectionLog
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


# Daily cleanup task for burglary alert images
# Daily cleanup task is now initialized in the main startup_event function below


# Lazy-load material classifier
_classifier_instance = None


def get_classifier():
    global _classifier_instance
    if _classifier_instance is None:
        print("Loading MaterialClassifier...")
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

    # Warmup classifier to prevent ClientDisconnect on first request
    try:
        get_classifier()
        print("Classifier warmup complete.")
    except Exception as e:
        print(f"Classifier warmup failed: {e}")


# ==================== COMMAND QUEUE (DATABASE) ====================


class Command(BaseModel):
    command: str
    params: Optional[dict] = {}
    timestamp: Optional[int] = None


@app.post("/api/bins/{bin_id}/command")
async def queue_command(bin_id: str, cmd: Command, db: Session = Depends(get_db)):
    """
    Queue a command for the bin to execute (e.g., OPEN, CLOSE).
    """
    import json

    new_cmd = CommandQueue(
        bin_id=bin_id,
        command=cmd.command,
        params=json.dumps(cmd.params) if cmd.params else "{}",
    )
    db.add(new_cmd)
    db.commit()

    print(f"✅ Queued DB command for {bin_id}: {cmd.command}")
    return {"status": "queued", "command": cmd.dict()}


@app.get("/api/bins/{bin_id}/commands")
async def get_commands(bin_id: str, db: Session = Depends(get_db)):
    """
    Get pending commands for a bin (Poll & Pop).
    """
    # Fetch pending commands
    pending_cmds = (
        db
        .query(CommandQueue)
        .filter(CommandQueue.bin_id == bin_id, CommandQueue.status == "pending")
        .all()
    )

    if not pending_cmds:
        return {"commands": []}

    # Convert to response format
    response_cmds = [cmd.to_dict() for cmd in pending_cmds]

    # Mark as executed (or delete)
    # For now, we delete to keep it simple like a queue
    for cmd in pending_cmds:
        db.delete(cmd)
    db.commit()

    print(f"🚀 Sent {len(response_cmds)} commands to {bin_id}")
    return {"commands": response_cmds}


@app.get("/api/bins/commands")
async def get_all_commands(db: Session = Depends(get_db)):
    """
    Get pending commands for BOTH bins in one request (low latency for device).
    Returns list of { "bin_id", "command", "params", "timestamp" }; each is removed after return.
    """
    pending_cmds = (
        db.query(CommandQueue)
        .filter(
            CommandQueue.bin_id.in_(["0x001", "0x002"]),
            CommandQueue.status == "pending",
        )
        .order_by(CommandQueue.created_at)
        .all()
    )
    if not pending_cmds:
        return {"commands": []}
    response_cmds = []
    for cmd in pending_cmds:
        d = cmd.to_dict()
        d["bin_id"] = cmd.bin_id
        response_cmds.append(d)
    for cmd in pending_cmds:
        db.delete(cmd)
    db.commit()
    print(f"🚀 Sent {len(response_cmds)} commands (combined)")
    return {"commands": response_cmds}


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

# Burglary Alert System
burglary_router = APIRouter(prefix="/api/v1/burglary")
burglary_router.include_router(auth_router)
burglary_router.include_router(alerts_router)
burglary_router.include_router(images_router)
burglary_router.include_router(telegram_router)
burglary_router.include_router(devices_router)
# Alias so app can call GET /api/v1/burglary/status (same as /api/v1/burglary/alert/status)
burglary_router.get("/status", response_model=SystemStatusResponse)(get_system_status)

app.include_router(burglary_router)


@app.get("/")
async def root():
    return {
        "message": "Student IoT Multi-Project Backend",
        "version": "2.2.0",
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
            "burglary_alert": {
                "prefix": "/api/v1/burglary",
                "endpoints": {
                    "login": "/api/v1/burglary/auth/login (POST)",
                    "alert": "/api/v1/burglary/alert/alert (POST)",
                    "feeds": "/api/v1/burglary/alert/feeds (GET)",
                    "image_upload": "/api/v1/burglary/image/image (POST)",
                    "telegram_config": "/api/v1/burglary/telegram/config (POST/GET)",
                },
            },
        },
    }


@app.post("/api/detect")
async def detect_material(
    request: Request,
    db: Session = Depends(get_db),
    classifier: MaterialClassifier = Depends(get_classifier),
):
    """
    Detect material type from uploaded image (RAW JPEG from ESP32-CAM).
    Accepts raw image/jpeg directly in request body.
    """
    try:
        import cv2  # Lazy import
        from starlette.requests import ClientDisconnect

        # Read raw image data from request body
        try:
            image_data = await request.body()
        except ClientDisconnect:
            # ESP32 disconnected during body read - retry won't help
            raise HTTPException(
                status_code=400,
                detail="Client disconnected before image upload completed",
            )

        print("\n📥 Detection request received:")
        print(f"   Content-Type: {request.headers.get('content-type')}")
        print(f"   Data size: {len(image_data)} bytes")

        if not image_data or len(image_data) == 0:
            raise HTTPException(status_code=400, detail="No image data received")

        # Convert bytes to numpy array
        nparr = np.frombuffer(image_data, np.uint8)

        # Decode image
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise HTTPException(
                status_code=400, detail="Invalid image - could not decode JPEG"
            )

        print(f"   ✅ Image decoded: {image.shape[1]}x{image.shape[0]} pixels")

        # Classify
        result = classifier.classify(image)

        print(
            f"   🤖 Detection: {result.get('material')} ({result.get('confidence') * 100:.1f}%)"
        )
        print(f"   Method: {result.get('method')}")

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

        # ==================== CLOUD COMMAND FALLBACK ====================
        # Automatically queue OPEN command for the detected bin
        # This allows the Main ESP32 to poll and open the bin even if ESP-NOW fails
        try:
            target_bin_id = None
            if result.get("material") == "ORGANIC":
                target_bin_id = "0x001"
            elif result.get("material") in ["NON_ORGANIC", "INORGANIC"]:
                target_bin_id = "0x002"

            if target_bin_id:
                print(f"   ☁️ Queueing fallback OPEN command for {target_bin_id}")

                # Persist to DB
                fallback_cmd = CommandQueue(
                    bin_id=target_bin_id,
                    command="OPEN",
                    params=json.dumps({
                        "source": "cloud_fallback",
                        "material": result.get("material"),
                        "confidence": result.get("confidence"),
                    }),
                )
                db.add(fallback_cmd)
                db.commit()

        except Exception as queue_err:
            print(f"   ⚠️ Failed to queue fallback command: {queue_err}")
        # ================================================================

        return result

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        print("❌ Error in detection endpoint:")
        print(f"   Exception: {e}")
        print(f"   Traceback:\n{error_trace}")

        # Log the error details
        try:
            error_log = DetectionLog(
                material="ERROR",
                confidence=0.0,
                method="error",
                bin_id="unknown",
                timestamp=datetime.now(),
                image_path=None,
            )
            db.add(error_log)
            db.commit()
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")


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
