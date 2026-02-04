from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
import uvicorn
import cv2
import numpy as np
from datetime import datetime
import os
from image_classifier import MaterialClassifier
from database import get_db, engine, Base
from models import Bin, DetectionLog, BinEvent

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Waste Bin Backend API", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize material classifier
model_path = os.getenv("MODEL_PATH", "models/material_classifier.pkl")
classifier = MaterialClassifier(model_path=model_path)

# Request/Response Models
class BinUpdate(BaseModel):
    bin_organic_id: str
    bin_non_organic_id: str
    organic_weight: Optional[float] = 0.0
    non_organic_weight: Optional[float] = 0.0
    organic_level: Optional[int] = None # Added level (0-100%)
    non_organic_level: Optional[int] = None # Added level (0-100%)
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

# ... (startup event remains same)

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    return {
        "message": "Smart Waste Bin Backend API",
        "version": "2.1.0",
        "database": "PostgreSQL",
        "endpoints": {
            "detect": "/api/detect (POST)",
            "bins": "/api/bins (GET)",
            "bin_status": "/api/bins/{bin_id} (GET)",
            "update_bins": "/api/bins/update (POST)",
            "events": "/api/events (GET)",
            "detections": "/api/detections (GET)"
        }
    }

# ... (detect_material remains same)

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
                full=data.organic_full
            )
            db.add(organic_bin)
        
        # Update non-organic bin
        non_organic_bin = db.query(Bin).filter(Bin.id == data.bin_non_organic_id).first()
        
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
                full=data.non_organic_full
            )
            db.add(non_organic_bin)
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Bins updated successfully"
        }
    
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
        "timestamp": datetime.now().isoformat()
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
        "timestamp": datetime.now().isoformat()
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
    
    return {
        "status": "success",
        "message": f"Bin {bin_id} reset successfully"
    }

@app.get("/api/events")
async def get_events(limit: int = 50, db: Session = Depends(get_db)):
    """
    Get recent bin events.
    """
    events = db.query(BinEvent).order_by(BinEvent.timestamp.desc()).limit(limit).all()
    return {
        "events": [event.to_dict() for event in events],
        "count": len(events)
    }

@app.get("/api/detections")
async def get_detections(limit: int = 50, db: Session = Depends(get_db)):
    """
    Get recent material detections.
    """
    detections = db.query(DetectionLog).order_by(DetectionLog.timestamp.desc()).limit(limit).all()
    return {
        "detections": [detection.to_dict() for detection in detections],
        "count": len(detections)
    }

@app.post("/api/bins/{bin_id}/event")
async def log_bin_event(bin_id: str, event_type: str, db: Session = Depends(get_db)):
    """
    Log a bin event (open, close, etc.).
    """
    event = BinEvent(bin_id=bin_id, event_type=event_type)
    db.add(event)
    db.commit()
    
    return {
        "status": "success",
        "event": event.to_dict()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
