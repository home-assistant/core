"""Fixtures for sma tests."""

from unittest.mock import patch

from pysma.const import GENERIC_SENSORS
from pysma.definitions import sensor_map
from pysma.sensor import Sensors
import pytest

from homeassistant import config_entries
from homeassistant.components.sma.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE["name"],
        unique_id=str(MOCK_DEVICE["serial"]),
        data=MOCK_USER_INPUT,
        source=config_entries.SOURCE_IMPORT,
        minor_version=2,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Create a fake SMA Config Entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("pysma.SMA.read"),
        patch(
            "pysma.SMA.get_sensors", return_value=Sensors(sensor_map[GENERIC_SENSORS])
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
