"""Tests for init module."""
from homeassistant.components.nws.const import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

from tests.common import MockConfigEntry
from tests.components.nws.const import NWS_CONFIG


async def test_unload_entry(hass, mock_simple_nws):
    """Test that nws setup with config yaml."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 2
    assert DOMAIN in hass.data

    assert len(hass.data[DOMAIN]) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0
    assert DOMAIN not in hass.data
