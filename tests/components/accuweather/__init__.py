"""Tests for AccuWeather."""
import json

from homeassistant.components.accuweather.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture


async def init_integration(hass, forecast=False) -> MockConfigEntry:
    """Set up the AccuWeather integration in Home Assistant."""
    if forecast:
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
            options={"forecast": True},
        )
    else:
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
        "accuweather.AccuWeather._async_get_data",
        return_value=json.loads(load_fixture("accuweather/location_data.json")),
    ), patch(
        "accuweather.AccuWeather.async_get_current_conditions",
        return_value=json.loads(
            load_fixture("accuweather/current_conditions_data.json")
        ),
    ), patch(
        "accuweather.AccuWeather.async_get_forecast",
        return_value=json.loads(load_fixture("accuweather/forecast_data.json")),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
