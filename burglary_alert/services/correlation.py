"""Alert-image correlation service."""

from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models.alert import Alert
from ..models.image import Image

CORRELATION_WINDOW_SECONDS = 5


def correlate_image_with_alert(image: Image, db: Session) -> Optional[Alert]:
    """
    Correlate an image with an alert based on timestamp proximity.

    Algorithm:
    1. Find uncorrelated alerts within last 10 seconds
    2. Match by timestamp proximity (within 5-second window)
    3. Link alert and image in database

    Args:
        image: Image object to correlate
        db: Database session

    Returns:
        Matched Alert object or None if no match found
    """
    # Find uncorrelated alerts within last 10 seconds
    time_window_start = image.timestamp - timedelta(seconds=10)
    time_window_end = image.timestamp + timedelta(seconds=CORRELATION_WINDOW_SECONDS)

    uncorrelated_alerts = (
        db
        .query(Alert)
        .filter(
            ~Alert.correlated,
            Alert.timestamp >= time_window_start,
            Alert.timestamp <= time_window_end,
        )
        .order_by(Alert.timestamp.desc())
        .all()
    )

    if not uncorrelated_alerts:
        return None

    # Find closest match by timestamp
    best_match = None
    min_time_diff = timedelta(seconds=CORRELATION_WINDOW_SECONDS)

    for alert in uncorrelated_alerts:
        time_diff = abs(alert.timestamp - image.timestamp)
        if time_diff < min_time_diff:
            min_time_diff = time_diff
            best_match = alert

    if best_match:
        # Link alert and image
        best_match.image_id = image.id
        best_match.correlated = True
        image.alert_id = best_match.id
        db.commit()
        db.refresh(best_match)

        print(
            f"✅ Correlated image {image.id} with alert {best_match.id} (time diff: {min_time_diff.total_seconds():.2f}s)"
        )
        return best_match

    return None
