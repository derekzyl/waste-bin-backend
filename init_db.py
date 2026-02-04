"""
Initialize database with default bins
Run this script once to set up the database
"""

from database import engine, Base
from models import Bin
from sqlalchemy.orm import sessionmaker

# Create all tables
Base.metadata.create_all(bind=engine)

# Create session
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Create default bins if they don't exist
    organic_bin = db.query(Bin).filter(Bin.id == "0x001").first()
    if not organic_bin:
        organic_bin = Bin(id="0x001", type="organic")
        db.add(organic_bin)
        print("Created organic bin (0x001)")
    
    non_organic_bin = db.query(Bin).filter(Bin.id == "0x002").first()
    if not non_organic_bin:
        non_organic_bin = Bin(id="0x002", type="non_organic")
        db.add(non_organic_bin)
        print("Created non-organic bin (0x002)")
    
    db.commit()
    print("Database initialized successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()

