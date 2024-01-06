"""Tests for the Smartfox integration."""
from __future__ import annotations

from homeassistant.components.smartfox.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "http://smartfox"


async def setup_fronius_integration(
    hass: HomeAssistant, is_logger: bool = True
) -> ConfigEntry:
    """Create the Fronius integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            "is_logger": is_logger,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
