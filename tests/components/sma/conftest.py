"""Fixtures for sma tests."""

from collections.abc import AsyncGenerator
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
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE["name"],
        unique_id=str(MOCK_DEVICE["serial"]),
        data=MOCK_USER_INPUT,
        source=config_entries.SOURCE_IMPORT,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_sma_client() -> AsyncGenerator[None]:
    """Mock the SMA client."""
    with (
        patch("pysma.SMA.read"),
        patch(
            "pysma.SMA.get_sensors", return_value=Sensors(sensor_map[GENERIC_SENSORS])
        ) as mock_client,
    ):
        yield mock_client
