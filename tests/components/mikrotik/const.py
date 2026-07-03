"""Constants for Mikrotik tests."""

HEALTH_DATA = [
    {"name": "voltage", "value": 24.2},
    {"name": "temperature", "value": 50.0},
]

SYSTEM_DATA = [
    {
        "cpu-load": 15,
        "total-memory": 1000,
        "free-memory": 200,
        "total-hdd-space": 100,
        "free-hdd-space": 25,
        "uptime": "1w2d3h4m5s",
    }
]
