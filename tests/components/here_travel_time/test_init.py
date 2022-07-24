"""The test for the HERE Travel Time integration."""

import pytest

from homeassistant.components.here_travel_time.config_flow import default_options
from homeassistant.components.here_travel_time.const import (
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
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


@pytest.mark.usefixtures("valid_response")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test that unloading an entry works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.data[DOMAIN]
