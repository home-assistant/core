"""The test for the HERE Travel Time integration."""

import pytest

from homeassistant.components.here_travel_time.config_flow import default_options
from homeassistant.components.here_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ROUTE_MODE,
    DOMAIN,
    METRIC_UNITS,
    ROUTE_MODE_FASTEST,
    TRAVEL_MODE_PUBLIC,
)
from homeassistant.const import CONF_API_KEY, CONF_MODE, CONF_NAME, CONF_UNIT_SYSTEM
from homeassistant.core import HomeAssistant

from .const import (
    API_KEY,
    DEFAULT_CONFIG,
    DESTINATION_LATITUDE,
    DESTINATION_LONGITUDE,
    ORIGIN_LATITUDE,
    ORIGIN_LONGITUDE,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("valid_response")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test that unloading an entry works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data=DEFAULT_CONFIG,
        options=default_options(hass),
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.data[DOMAIN]


@pytest.mark.usefixtures("valid_response")
async def test_migrate_1_to_2(hass: HomeAssistant) -> None:
    """Test that migration from version 1 to 2 works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: "publicTransportTimeTable",
            CONF_NAME: "test",
        },
        options={
            "traffic_mode": "traffic_enabled",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_ARRIVAL_TIME: None,
            CONF_DEPARTURE_TIME: None,
            CONF_UNIT_SYSTEM: METRIC_UNITS,
        },
    )
    entry.add_to_hass(hass)
    assert entry.version == 1

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check that it has a source_id now
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)

    assert updated_entry.version == 2
    assert updated_entry.data[CONF_MODE] == TRAVEL_MODE_PUBLIC
    assert "traffic_mode" not in updated_entry.options
