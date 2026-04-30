from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from astral import LocationInfo
from astral.sun import sun


def get_lighting_label(
    dt: datetime,
    latitude: float,
    longitude: float,
    window_minutes: int,
    local_timezone: str = "UTC",
) -> str:
    """Return 'day', 'night', 'sunrise', or 'sunset' for a given UTC datetime."""
    tz = ZoneInfo(local_timezone)
    local_date = dt.astimezone(tz).date()
    location = LocationInfo(latitude=latitude, longitude=longitude, timezone=local_timezone)
    s = sun(location.observer, date=local_date, tzinfo=tz)
    sunrise = s["sunrise"].astimezone(timezone.utc)
    sunset = s["sunset"].astimezone(timezone.utc)
    window = timedelta(minutes=window_minutes)

    if abs(dt - sunrise) <= window:
        return "sunrise"
    if abs(dt - sunset) <= window:
        return "sunset"
    if sunrise + window < dt < sunset - window:
        return "day"
    return "night"
