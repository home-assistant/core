"""Tests for the Arve integration."""

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ACC_TOKEN_SELECTION = {CONF_ACCESS_TOKEN: "249e597c-e0cc-436e-abbd-867d61d6c5a9"}

CLIENT_SECRET_SELECTION = {CONF_CLIENT_SECRET: "73bdb639-a454-4f9e-879c-793ee39bb268"}

USER_INPUT = (
    ACC_TOKEN_SELECTION | CLIENT_SECRET_SELECTION | {CONF_NAME: "A0120-0000-0000-1780"}
)


async def async_init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Arve integration for testing."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
