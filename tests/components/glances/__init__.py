"""Tests for Glances."""

from datetime import datetime
from typing import Any

MOCK_USER_INPUT: dict[str, Any] = {
    "host": "0.0.0.0",
    "username": "username",
    "password": "password",
    "port": 61208,
    "ssl": False,
    "verify_ssl": True,
}

MOCK_REFERENCE_DATE: datetime = datetime.fromisoformat("2024-02-13T14:13:12")

HA_SENSOR_DATA: dict[str, Any] = {
    "fs": {
        "/ssl": {"disk_use": 30.7, "disk_use_percent": 6.7, "disk_free": 426.5},
        "/media": {"disk_use": 30.7, "disk_use_percent": 6.7, "disk_free": 426.5},
    },
    "diskio": {
        "nvme0n1": {"read": 184320, "write": 23863296},
        "sda": {"read": 3859, "write": 25954},
    },
    "sensors": {
        "cpu_thermal 1": {"temperature_core": 59},
        "err_temp": {"temperature_hdd": "unavailable"},
        "na_temp": {"temperature_hdd": "unavailable"},
    },
    "mem": {
        "memory_use_percent": 27.6,
        "memory_use": 1047.1,
        "memory_free": 2745.0,
    },
    "docker": {"docker_active": 2, "docker_cpu_use": 77.2, "docker_memory_use": 1149.6},
    "raid": {
        "md3": {
            "status": "active",
            "type": "raid1",
            "components": {"sdh1": "2", "sdi1": "0"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
        "md1": {
            "status": "active",
            "type": "raid1",
            "components": {"sdg": "0", "sde": "1"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
    },
    "network": {
        "lo": {"is_up": True, "rx": 7646, "tx": 7646, "speed": 0.0},
        "dummy0": {"is_up": False, "rx": 0.0, "tx": 0.0, "speed": 0.0},
        "eth0": {"is_up": True, "rx": 3953, "tx": 5995, "speed": 9.8},
    },
    "uptime": "3 days, 10:25:20",
    "gpu": {
        "NVIDIA GeForce RTX 3080 (GPU 0)": {
            "temperature": 51,
            "mem": 8.41064453125,
            "proc": 26,
            "fan_speed": 0,
        }
    },
}
