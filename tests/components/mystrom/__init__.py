"""Tests for the myStrom integration."""
from typing import Any


def get_default_device_response(device_type: int) -> dict[str, Any]:
    """Return default device response."""
    return {
        "version": "2.59.32",
        "mac": "6001940376EB",
        "type": device_type,
        "ssid": "personal",
        "ip": "192.168.0.23",
        "mask": "255.255.255.0",
        "gw": "192.168.0.1",
        "dns": "192.168.0.1",
        "static": False,
        "connected": True,
        "signal": 94,
    }
