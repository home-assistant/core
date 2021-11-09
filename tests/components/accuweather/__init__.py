"""Tests for AccuWeather."""
import json
from unittest.mock import PropertyMock, patch

from homeassistant.components.accuweather.const import DOMAIN

from tests.common import MockConfigEntry, load_fixture


async def init_integration(
    hass, forecast=False, unsupported_icon=False
) -> MockConfigEntry:
    """Set up the AccuWeather integration in Home Assistant."""
    options = {}
    if forecast:
        options["forecast"] = True

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
        options=options,
    )

    current = json.loads(load_fixture("accuweather/current_conditions_data.json"))
    forecast = json.loads(load_fixture("accuweather/forecast_data.json"))

    if unsupported_icon:
        current["WeatherIcon"] = 999

    with patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
        return_value=current,
    ), patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_forecast",
        return_value=forecast,
    ), patch(
        "homeassistant.components.accuweather.AccuWeather.requests_remaining",
        new_callable=PropertyMock,
        return_value=10,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
