"""Tests for Deutscher Wetterdienst (DWD) Weather Warnings integration."""

from typing import Final

from homeassistant.components.dwd_weather_warnings.const import (
    CONF_REGION_IDENTIFIER,
    DEFAULT_MONITORED_CONDITIONS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEMO_CONFIG_ENTRY: Final = {
    CONF_NAME: "Unit Test",
    CONF_REGION_IDENTIFIER: "807111000",
    CONF_MONITORED_CONDITIONS: DEFAULT_MONITORED_CONDITIONS,
}


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Test loading and unloading the integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]
