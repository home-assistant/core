"""The test for the HERE Travel Time integration."""

from datetime import datetime

import pytest

from homeassistant.components.here_travel_time.config_flow import DEFAULT_OPTIONS
from homeassistant.components.here_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_ROUTE_MODE,
    DOMAIN,
    ROUTE_MODE_FASTEST,
)
from homeassistant.core import HomeAssistant

from .const import DEFAULT_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("valid_response")
@pytest.mark.parametrize(
    "options",
    [
        DEFAULT_OPTIONS,
        {
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_DEPARTURE_TIME: datetime.now(),
        },
        {
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_ARRIVAL_TIME: datetime.now(),
        },
        {
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        },
    ],
)
async def test_unload_entry(hass: HomeAssistant, options) -> None:
    """Test that unloading an entry works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data=DEFAULT_CONFIG,
        options=options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.data[DOMAIN]
