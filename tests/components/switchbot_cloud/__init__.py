"""Tests for the SwitchBot Cloud integration."""

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        CONF_API_TOKEN: "test-token",
        CONF_API_KEY: "test-api-key",
    }
    entry = MockConfigEntry(
        domain=DOMAIN, data=config, entry_id="123456", unique_id="123456"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
