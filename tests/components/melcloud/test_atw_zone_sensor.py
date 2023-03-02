"""Test the MELCloud ATW zone sensor."""
from unittest.mock import patch

import pytest

from homeassistant.components.melcloud.sensor import ATW_ZONE_SENSORS, AtwZoneSensor


@pytest.fixture
def mock_device():
    """Mock MELCloud device."""
    with patch("homeassistant.components.melcloud.MelCloudDevice") as mock:
        mock.name = "name"
        mock.device.serial = 1234
        mock.device.mac = "11:11:11:11:11:11"
        yield mock


@pytest.fixture
def mock_zone_1():
    """Mock zone 1."""
    with patch("pymelcloud.atw_device.Zone") as mock:
        mock.zone_index = 1
        yield mock


@pytest.fixture
def mock_zone_2():
    """Mock zone 2."""
    with patch("pymelcloud.atw_device.Zone") as mock:
        mock.zone_index = 2
        yield mock


def test_zone_unique_ids(mock_device, mock_zone_1, mock_zone_2) -> None:
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
