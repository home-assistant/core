"""The test for the HERE Travel Time integration."""

from homeassistant.components.here_travel_time.const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    DOMAIN,
    TRAVEL_MODE_CAR,
)
from homeassistant.const import CONF_API_KEY, CONF_MODE, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import (
    API_KEY,
    CAR_DESTINATION_LATITUDE,
    CAR_DESTINATION_LONGITUDE,
    CAR_ORIGIN_LATITUDE,
    CAR_ORIGIN_LONGITUDE,
)

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant, valid_response):
    """Test that unloading an entry works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN: f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
            CONF_DESTINATION: f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_NAME: "test",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.data[DOMAIN]
