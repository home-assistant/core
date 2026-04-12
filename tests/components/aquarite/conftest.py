"""Shared fixtures for Aquarite tests."""
from __future__ import annotations

from typing import Any

import pytest

MOCK_USERNAME = "testuser@example.com"
MOCK_PASSWORD = "testpassword"
MOCK_POOL_ID = "ABCDEF1234567890"
MOCK_POOL_NAME = "My Pool"


@pytest.fixture
def mock_pool_data() -> dict[str, Any]:
    """Return mock coordinator pool data."""
    return {
        "main": {
            "temperature": 25.5,
            "version": 825,
            "RSSI": -65,
            "hasCD": 0,
            "hasCL": 0,
            "hasPH": 1,
            "hasRX": 1,
            "hasUV": 0,
            "hasHidro": 1,
            "hasIO": 0,
            "hasLED": 0,
            "localTime": 1775995380,
        },
        "modules": {
            "ph": {
                "current": "742",
                "tank": 0,
                "pump_high_on": 0,
                "pump_low_on": 0,
                "al3": 0,
                "status": {"low_value": "650", "high_value": "751"},
            },
            "rx": {
                "current": 707,
                "tank": 0,
                "status": {"value": 700},
                "pump_status": 0,
            },
        },
        "hidro": {
            "current": 50,
            "level": 100,
            "fl1": 0,
            "fl2": 0,
            "low": 0,
            "cover": 0,
            "cover_enabled": 0,
            "cloration_enabled": 0,
            "maxAllowedValue": 220,
            "is_electrolysis": True,
        },
        "filtration": {
            "status": 1,
            "mode": 1,
            "manVel": 2,
            "interval1": {"from": 28800, "to": 36000},
            "interval2": {"from": 46800, "to": 50400},
            "interval3": {"from": 68400, "to": 70200},
            "timerVel1": 1,
            "timerVel2": 1,
            "timerVel3": 0,
            "intel": {"time": "600", "temp": 24},
        },
        "light": {"status": 0},
        "relays": {
            "relay1": {"info": {"onoff": 0, "status": 0}},
            "relay2": {"info": {"onoff": 0, "status": 0}},
            "relay3": {"info": {"onoff": 0, "status": 0}},
            "relay4": {"info": {"onoff": 0, "status": 0}},
            "filtration": {"heating": {"status": 0}},
        },
        "backwash": {"status": 0},
        "form": {
            "lat": "50.7",
            "lng": "4.4",
            "city": "Waterloo",
            "street": "Rue Test",
            "zipcode": "1410",
            "country": "BE",
        },
        "present": True,
    }


def get_value(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """Navigate nested dicts using dot-notation path (mirrors AquariteClient.get_value)."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
