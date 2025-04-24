"""Tests for the Autoskope integration."""

from unittest.mock import MagicMock

# Define mock data based on TypedDicts in models.py
MOCK_VEHICLE_INFO_1: dict = {
    "id": "12345",
    "name": "Test Vehicle 1",
    "ex_pow": 12.8,
    "bat_pow": 4.2,
    "hdop": 1.1,
    "support_infos": {"imei": "IMEI12345"},
    "device_type_id": "10",  # Corresponds to Autoskope V3
}

MOCK_POSITION_FEATURE_1: dict = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [13.37, 52.52]},  # lon, lat
    "properties": {
        "s": 0.0,  # speed
        "dt": "2024-04-17T10:00:00Z",  # timestamp
        "park": True,  # park_mode
        "carid": "12345",  # vehicle id matching MOCK_VEHICLE_INFO_1
    },
}


def create_mock_vehicle(vehicle_id: str, name: str) -> MagicMock:
    """Create a mock vehicle for testing."""
    vehicle = MagicMock()
    vehicle.id = vehicle_id
    vehicle.name = name

    # Create mock position data
    position = MagicMock()
    position.latitude = 12.345
    position.longitude = 45.678
    position.speed = 0.0
    position.timestamp = "2023-01-01T12:00:00Z"
    position.park_mode = True

    # Set common properties
    vehicle.position = position
    vehicle.model = "AutoskopeX"
    vehicle.imei = f"IMEI{vehicle_id}"
    vehicle.external_voltage = 12.5
    vehicle.battery_voltage = 4.1
    vehicle.gps_quality = 0.95

    return vehicle
