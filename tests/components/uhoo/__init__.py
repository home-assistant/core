"""Tests for uhoo-homeassistant integration."""

from homeassistant.components.uhoo.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def setup_uhoo_config(hass: HomeAssistant):
    """Load a mock config for uHoo."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
