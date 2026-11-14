"""Cosntants for the Sense integration tests."""

MONITOR_ID = "12345"

MOCK_CONFIG = {
    "timeout": 6,
    "email": "test-email",
    "password": "test-password",
    "access_token": "ABC",
    "user_id": "123",
    "monitor_id": MONITOR_ID,
    "device_id": "789",
    "refresh_token": "XYZ",
}


DEVICE_1_NAME = "Car"
DEVICE_1_ID = "abc123"
DEVICE_1_ICON = "car-electric"
DEVICE_1_POWER = 100.0
DEVICE_1_DAY_ENERGY = 500

DEVICE_2_NAME = "Oven"
DEVICE_2_ID = "def456"
DEVICE_2_ICON = "stove"
DEVICE_2_POWER = 50.0
DEVICE_2_DAY_ENERGY = 42

# Energy the mocked monitor reports for every completed hour, per trend variant.
HOURLY_ENERGY = {
    "usage": 1.5,
    "production": 0.75,
    "from_grid": 1.0,
    "to_grid": 0.25,
    "net_production": -0.75,
    "production_pct": 50,
    "solar_powered": 50,
}

# Period-to-date reading the mocked monitor reports for every trend scale.
PERIOD_TO_DATE = 15
