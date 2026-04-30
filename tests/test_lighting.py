from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import patch, MagicMock
from src.lighting import get_lighting_label


LAT = 41.8781
LON = -87.6298
WINDOW = 30  # minutes


def _utc(hour, minute=0):
    return datetime(2026, 4, 30, hour, minute, tzinfo=timezone.utc)


def _make_sun(sunrise_hour=11, sunset_hour=23):
    """Return mock sun dict with UTC times (Chicago ~UTC-5 in CDT, so 6am local = 11am UTC)."""
    return {
        "sunrise": _utc(sunrise_hour),
        "sunset": _utc(sunset_hour),
    }


def test_label_day():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        label = get_lighting_label(_utc(14), LAT, LON, WINDOW)
    assert label == "day"


def test_label_night_before_sunrise():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        label = get_lighting_label(_utc(5), LAT, LON, WINDOW)
    assert label == "night"


def test_label_night_after_sunset():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        label = get_lighting_label(_utc(23, 45), LAT, LON, WINDOW)
    assert label == "night"


def test_label_sunrise_window():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        # 15 minutes before sunrise = inside window
        label = get_lighting_label(_utc(10, 45), LAT, LON, WINDOW)
    assert label == "sunrise"


def test_label_sunset_window():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        # 10 minutes after sunset = inside window
        label = get_lighting_label(_utc(23, 10), LAT, LON, WINDOW)
    assert label == "sunset"
