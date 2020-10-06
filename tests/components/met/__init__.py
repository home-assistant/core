"""Tests for Met.no."""
from homeassistant.components.met.const import DOMAIN
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Met integration in Home Assistant."""
    entry_data = {
        CONF_NAME: "test",
        CONF_LATITUDE: 0,
        CONF_LONGITUDE: 0,
        CONF_ELEVATION: 0,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    with patch(
        "homeassistant.components.met.metno.MetWeatherData.fetching_data",
        return_value=True,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
