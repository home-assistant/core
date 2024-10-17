"""Cosntants for the Sense integration tests."""

MOCK_CONFIG = {
    "timeout": 6,
    "email": "test-email",
    "password": "test-password",
    "access_token": "ABC",
    "user_id": "123",
    "monitor_id": "456",
    "device_id": "789",
    "refresh_token": "XYZ",
}

DEVICE_1_NAME = "Car"
DEVICE_1_ID = "abc123"
DEVICE_1_ICON = "car-electric"
DEVICE_1_POWER = 100.0

DEVICE_1_DATA = {
    "name": DEVICE_1_NAME,
    "id": DEVICE_1_ID,
    "icon": "car",
    "tags": {"DeviceListAllowed": "true"},
    "w": DEVICE_1_POWER,
}

DEVICE_2_NAME = "Oven"
DEVICE_2_ID = "def456"
DEVICE_2_ICON = "stove"
DEVICE_2_POWER = 50.0

DEVICE_2_DATA = {
    "name": DEVICE_2_NAME,
    "id": DEVICE_2_ID,
    "icon": "stove",
    "tags": {"DeviceListAllowed": "true"},
    "w": DEVICE_2_POWER,
}
MONITOR_ID = "12345"
