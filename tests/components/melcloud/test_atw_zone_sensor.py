"""Test the MELCloud ATW zone sensor."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.melcloud.sensor import ATW_ZONE_SENSORS, AtwZoneSensor


@pytest.fixture
def mock_coordinator():
    """Mock MELCloud coordinator."""
    with patch(
        "homeassistant.components.melcloud.coordinator.MelCloudDeviceUpdateCoordinator"
    ) as mock:
        yield mock


@pytest.fixture
def mock_device(mock_coordinator):
    """Mock MELCloud device."""
    mock = MagicMock()
    mock.name = "name"
    mock.device.serial = 1234
    mock.device.mac = "11:11:11:11:11:11"
    mock.zone_device_info.return_value = {}
    mock.coordinator = mock_coordinator
    return mock


@pytest.fixture
def mock_zone_1():
    """Mock zone 1."""
    mock = MagicMock()
    mock.zone_index = 1
    return mock


@pytest.fixture
def mock_zone_2():
    """Mock zone 2."""
    mock = MagicMock()
    mock.zone_index = 2
    return mock


def test_zone_unique_ids(
    mock_coordinator: MagicMock,
    mock_device: MagicMock,
    mock_zone_1: MagicMock,
    mock_zone_2: MagicMock,
) -> None:
    """Test unique id generation correctness."""
    sensor_1 = AtwZoneSensor(
        mock_device,
        mock_zone_1,
        ATW_ZONE_SENSORS[0],  # room_temperature
    )
    assert sensor_1.unique_id == "1234-11:11:11:11:11:11-room_temperature"

    sensor_2 = AtwZoneSensor(
        mock_device,
        mock_zone_2,
        ATW_ZONE_SENSORS[0],  # room_temperature
    )
    assert sensor_2.unique_id == "1234-11:11:11:11:11:11-room_temperature-zone-2"


def test_zone_flow_temperature_unique_ids(
    mock_coordinator: MagicMock,
    mock_device: MagicMock,
    mock_zone_1: MagicMock,
    mock_zone_2: MagicMock,
) -> None:
    """Test unique id generation for zone flow temperature."""
    sensor_1 = AtwZoneSensor(
        mock_device,
        mock_zone_1,
        ATW_ZONE_SENSORS[1],  # zone_flow_temperature
    )
    assert sensor_1.unique_id == "1234-11:11:11:11:11:11-flow_temperature"

    sensor_2 = AtwZoneSensor(
        mock_device,
        mock_zone_2,
        ATW_ZONE_SENSORS[1],  # zone_flow_temperature
    )
    assert sensor_2.unique_id == "1234-11:11:11:11:11:11-flow_temperature-zone-2"


def test_zone_return_temperature_unique_ids(
    mock_coordinator: MagicMock,
    mock_device: MagicMock,
    mock_zone_1: MagicMock,
    mock_zone_2: MagicMock,
) -> None:
    """Test unique id generation for zone return temperature."""
    sensor_1 = AtwZoneSensor(
        mock_device,
        mock_zone_1,
        ATW_ZONE_SENSORS[2],  # zone_return_temperature
    )
    assert sensor_1.unique_id == "1234-11:11:11:11:11:11-return_temperature"

    sensor_2 = AtwZoneSensor(
        mock_device,
        mock_zone_2,
        ATW_ZONE_SENSORS[2],  # zone_return_temperature
    )
    assert sensor_2.unique_id == "1234-11:11:11:11:11:11-return_temperature-zone-2"
