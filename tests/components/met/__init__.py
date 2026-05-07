"""Tests for Met.no."""

from unittest.mock import patch

from homeassistant.components.met.const import (
    CONF_TRACK_HOME,
    DOMAIN,
    HOME_LOCATION_NAME,
)
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, track_home: bool = False
) -> MockConfigEntry:
    """Set up the Met integration in Home Assistant."""
    entry_data = {
        CONF_LATITUDE: 0,
        CONF_LONGITUDE: 1.0,
        CONF_ELEVATION: 1.0,
    }

    if track_home:
        entry_data = {CONF_TRACK_HOME: True}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        title=HOME_LOCATION_NAME if track_home else "",
        minor_version=2,
    )
    with patch(
        "homeassistant.components.met.coordinator.metno.MetWeatherData.fetching_data",
        return_value=True,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
