"""Tests for the IOmeter integration."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Fixture for setting up the IOmeter platform."""
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.iometer.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


def get_reading_callback(mock: MagicMock) -> Callable:
    """Get the reading callback registered with the SSE client."""
    return mock.subscribe_readings.call_args[0][0]


def get_status_callback(mock: MagicMock) -> Callable:
    """Get the status callback registered with the SSE client."""
    return mock.subscribe_status.call_args[0][0]


def get_reading_error_callback(mock: MagicMock) -> Callable:
    """Get the reading error callback registered with the SSE client."""
    return mock.subscribe_readings.call_args[0][1]


def get_status_error_callback(mock: MagicMock) -> Callable:
    """Get the status error callback registered with the SSE client."""
    return mock.subscribe_status.call_args[0][1]
