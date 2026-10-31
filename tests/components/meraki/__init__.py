"""Tests for the Meraki integration."""

from unittest.mock import MagicMock

from meraki import APIError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Meraki integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def api_error(status: int) -> APIError:
    """Return an error like the Meraki library raises it."""
    response = MagicMock(status_code=status, reason_phrase="Error")
    response.json.return_value = {"errors": ["Error"]}
    return APIError({"tags": ["organizations"], "operation": "test"}, response)
