"""Tests for the Arve integration."""

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_ACCESS_TOKEN: "test-access-token",
    CONF_CLIENT_SECRET: "test-customer-token",
}


async def async_init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Arve integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
