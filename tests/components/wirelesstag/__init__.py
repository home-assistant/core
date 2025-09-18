"""Tests for the Wireless Sensor Tag integration."""

from __future__ import annotations

MOCK_TAGS = {
    "tag1": {
        "uuid": "tag1",
        "name": "Living Room",
        "is_alive": True,
        "battery_remaining": 0.8,
        "mac": "00:11:22:33:44:55",
    },
    "tag2": {
        "uuid": "tag2",
        "name": "Bedroom",
        "is_alive": True,
        "battery_remaining": 0.6,
        "mac": "00:11:22:33:44:56",
    },
}
