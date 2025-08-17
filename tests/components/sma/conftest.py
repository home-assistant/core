"""Fixtures for sma tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pysma.const import (
    ENERGY_METER_VIA_INVERTER,
    GENERIC_SENSORS,
    OPTIMIZERS_VIA_INVERTER,
)
from pysma.definitions import sensor_map
from pysma.sensor import Sensors
import pytest

from homeassistant.components.sma.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE["name"],
        unique_id=str(MOCK_DEVICE["serial"]),
        data=MOCK_USER_INPUT,
        minor_version=2,
        entry_id="sma_entry_123",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.sma.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_sma_client() -> Generator[MagicMock]:
    """Mock the SMA client."""
    with patch("homeassistant.components.sma.pysma.SMA", autospec=True) as client:
        client.return_value.device_info.return_value = MOCK_DEVICE
        client.new_session.return_value = True
        client.return_value.get_sensors.return_value = Sensors(
            sensor_map[GENERIC_SENSORS]
            + sensor_map[OPTIMIZERS_VIA_INVERTER]
            + sensor_map[ENERGY_METER_VIA_INVERTER]
        )

        default_sensor_values = {
            "6100_00499100": 5000,
            "6100_00499500": 230,
            "6100_00499200": 20,
            "6100_00499300": 50,
            "6100_00499400": 100,
            "6100_00499600": 10,
            "6100_00499700": 1000,
        }

        def mock_read(sensors):
            for sensor in sensors:
                if sensor.key in default_sensor_values:
                    sensor.value = default_sensor_values[sensor.key]
            return True

        client.return_value.read.side_effect = mock_read

        yield client
