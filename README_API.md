# Energy Audit Backend API

## Overview
FastAPI extension for the Smart Energy Auditing System.
Integrated into the existing `smart-waste-bin` backend.

## New Endpoints (`/energy/...`)
-   `POST /energy/readings`: Accept sensor data from ESP32.
-   `GET /energy/readings/{id}`: Get stored readings.
-   `GET /energy/audit/{id}/alerts`: Get generated waste alerts.
-   `POST /energy/devices`: Register new devices.

## Setup
1.  Navigate to `backend/`.
2.  Install dependencies (if not already): `pip install -r requirements.txt`.
3.  Run Server:
    ```bash
    uvicorn main:app --reload --host 0.0.0.0
    ```
4.  Swagger Docs: `http://localhost:8000/docs`.

## Database
-   Tables `energy_devices`, `energy_sensor_readings`, etc., are created on startup.
-   Uses SQLite/PostgreSQL as configured in `database.py`.
