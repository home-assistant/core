"""Tests for Airly."""
import json

from homeassistant.components.airly.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture


async def init_integration(hass, forecast=False) -> MockConfigEntry:
    """Set up the Airly integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="55.55-122.12",
        data={
            "api_key": "foo",
            "latitude": 55.55,
            "longitude": 122.12,
            "name": "Home",
        },
    )

    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_valid_station.json")),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
