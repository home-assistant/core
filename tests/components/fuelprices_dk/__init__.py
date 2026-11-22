"""Tests for the Danish Fuelprices integration."""

from unittest.mock import Mock

from aiohttp import ClientResponseError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


def client_error(status: int) -> ClientResponseError:
    """Create an HTTP response error."""
    return ClientResponseError(
        request_info=Mock(), history=(), status=status, message="error", headers=None
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration from a mock config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
