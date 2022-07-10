"""Tests for Climacell weather entity."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.climacell.const import (
    ATTR_CLOUD_COVER,
    ATTR_PRECIPITATION_TYPE,
    ATTR_WIND_GUST,
    ATTRIBUTION,
    DOMAIN,
)
from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from .const import API_V3_ENTRY_DATA

from tests.common import MockConfigEntry


@callback
def _enable_entity(hass: HomeAssistant, entity_name: str) -> None:
    """Enable disabled entity."""
    ent_reg = async_get(hass)
    entry = ent_reg.async_get(entity_name)
    updated_entry = ent_reg.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False


async def _setup(hass: HomeAssistant, config: dict[str, Any]) -> State:
    """Set up entry and return entity state."""
    with patch(
        "homeassistant.util.dt.utcnow",
        return_value=datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config,
            unique_id="test",
            version=1,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        for entity_name in ("hourly", "nowcast"):
            _enable_entity(hass, f"weather.climacell_{entity_name}")
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 3

    return hass.states.get("weather.climacell_daily")


async def test_v3_weather(
    hass: HomeAssistant,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test v3 weather data."""
    weather_state = await _setup(hass, API_V3_ENTRY_DATA)
    assert weather_state.state == ATTR_CONDITION_SUNNY
    assert weather_state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert weather_state.attributes[ATTR_FORECAST] == [
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SUNNY,
            ATTR_FORECAST_TIME: "2021-03-07T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 7.2,
            ATTR_FORECAST_TEMP_LOW: -4.7,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-08T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 9.7,
            ATTR_FORECAST_TEMP_LOW: -4.0,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-09T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 19.4,
            ATTR_FORECAST_TEMP_LOW: -0.3,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-10T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 18.5,
            ATTR_FORECAST_TEMP_LOW: 3.0,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-11T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 5,
            ATTR_FORECAST_TEMP: 19.7,
            ATTR_FORECAST_TEMP_LOW: 9.3,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-12T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 0.05,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 19.9,
            ATTR_FORECAST_TEMP_LOW: 12.1,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-13T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 15.8,
            ATTR_FORECAST_TEMP_LOW: 7.5,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_RAINY,
            ATTR_FORECAST_TIME: "2021-03-14T00:00:00-08:00",
            ATTR_FORECAST_PRECIPITATION: 1.07,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 75,
            ATTR_FORECAST_TEMP: 6.4,
            ATTR_FORECAST_TEMP_LOW: 3.2,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SNOWY,
            ATTR_FORECAST_TIME: "2021-03-15T00:00:00-07:00",  # DST starts
            ATTR_FORECAST_PRECIPITATION: 7.31,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 95,
            ATTR_FORECAST_TEMP: 1.2,
            ATTR_FORECAST_TEMP_LOW: 0.2,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-16T00:00:00-07:00",
            ATTR_FORECAST_PRECIPITATION: 0.01,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 5,
            ATTR_FORECAST_TEMP: 6.1,
            ATTR_FORECAST_TEMP_LOW: -1.6,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-17T00:00:00-07:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 11.3,
            ATTR_FORECAST_TEMP_LOW: 1.3,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-18T00:00:00-07:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 5,
            ATTR_FORECAST_TEMP: 12.3,
            ATTR_FORECAST_TEMP_LOW: 5.6,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-19T00:00:00-07:00",
            ATTR_FORECAST_PRECIPITATION: 0.18,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 45,
            ATTR_FORECAST_TEMP: 9.4,
            ATTR_FORECAST_TEMP_LOW: 4.7,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_RAINY,
            ATTR_FORECAST_TIME: "2021-03-20T00:00:00-07:00",
            ATTR_FORECAST_PRECIPITATION: 1.23,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 55,
            ATTR_FORECAST_TEMP: 5.0,
            ATTR_FORECAST_TEMP_LOW: 3.1,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-21T00:00:00-07:00",
            ATTR_FORECAST_PRECIPITATION: 0.04,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 20,
            ATTR_FORECAST_TEMP: 6.8,
            ATTR_FORECAST_TEMP_LOW: 0.9,
        },
    ]
    assert weather_state.attributes[ATTR_FRIENDLY_NAME] == "ClimaCell - Daily"
    assert weather_state.attributes[ATTR_WEATHER_HUMIDITY] == 24
    assert weather_state.attributes[ATTR_WEATHER_OZONE] == 52.625
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE] == 1028.12
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE] == 6.6
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY] == 9.99
    assert weather_state.attributes[ATTR_WEATHER_WIND_BEARING] == 320.31
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED] == 14.63
    assert weather_state.attributes[ATTR_CLOUD_COVER] == 100
    assert weather_state.attributes[ATTR_WIND_GUST] == 24.0758
    assert weather_state.attributes[ATTR_PRECIPITATION_TYPE] == "rain"
