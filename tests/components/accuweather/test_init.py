"""Test init of AccuWeather integration."""
from homeassistant.components.accuweather.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.components.accuweather import init_integration


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"


async def test_config_not_ready(hass):
    """Test for setup failure if connection to AccuWeather is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data={
            "api_key": "32-character-string-1234567890qw",
            "latitude": 55.55,
            "longitude": 122.12,
            "name": "Home",
        },
    )

    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        side_effect=ConnectionError(),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
