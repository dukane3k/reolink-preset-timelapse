from __future__ import annotations
from datetime import datetime, timedelta, timezone
from astral import LocationInfo
from astral.sun import sun


def get_lighting_label(
    dt: datetime,
    latitude: float,
    longitude: float,
    window_minutes: int,
) -> str:
    """Return 'day', 'night', 'sunrise', or 'sunset' for a given UTC datetime."""
    location = LocationInfo(latitude=latitude, longitude=longitude)
    s = sun(location.observer, date=dt.date(), tzinfo=timezone.utc)
    sunrise = s["sunrise"]
    sunset = s["sunset"]
    window = timedelta(minutes=window_minutes)

    if abs(dt - sunrise) <= window:
        return "sunrise"
    if abs(dt - sunset) <= window:
        return "sunset"
    if sunrise + window < dt < sunset - window:
        return "day"
    return "night"
