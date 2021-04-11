"""Tests for Climacell weather entity."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from unittest.mock import patch

import pytest
import pytz

from homeassistant.components.climacell.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
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
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
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
from homeassistant.core import State
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.typing import HomeAssistantType

from .const import API_V3_ENTRY_DATA, API_V4_ENTRY_DATA

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def _enable_entity(hass: HomeAssistantType, entity_name: str) -> None:
    """Enable disabled entity."""
    ent_reg = async_get(hass)
    entry = ent_reg.async_get(entity_name)
    updated_entry = ent_reg.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False


async def _setup(hass: HomeAssistantType, config: dict[str, Any]) -> State:
    """Set up entry and return entity state."""
    with patch(
        "homeassistant.util.dt.utcnow",
        return_value=datetime(2021, 3, 6, 23, 59, 59, tzinfo=pytz.UTC),
    ):
        data = _get_config_schema(hass)(config)
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=data,
            unique_id=_get_unique_id(hass, data),
            version=1,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await _enable_entity(hass, "weather.climacell_hourly")
        await _enable_entity(hass, "weather.climacell_nowcast")
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 3

    return hass.states.get("weather.climacell_daily")


async def test_v3_weather(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test v3 weather data."""
    weather_state = await _setup(hass, API_V3_ENTRY_DATA)
    assert weather_state.state == ATTR_CONDITION_SUNNY
    assert weather_state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert weather_state.attributes[ATTR_FORECAST] == [
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SUNNY,
            ATTR_FORECAST_TIME: "2021-03-07T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 7,
            ATTR_FORECAST_TEMP_LOW: -5,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-08T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 10,
            ATTR_FORECAST_TEMP_LOW: -4,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-09T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 19,
            ATTR_FORECAST_TEMP_LOW: 0,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-10T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 18,
            ATTR_FORECAST_TEMP_LOW: 3,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-11T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 5,
            ATTR_FORECAST_TEMP: 20,
            ATTR_FORECAST_TEMP_LOW: 9,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-12T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0.04572,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 20,
            ATTR_FORECAST_TEMP_LOW: 12,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-13T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 16,
            ATTR_FORECAST_TEMP_LOW: 7,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_RAINY,
            ATTR_FORECAST_TIME: "2021-03-14T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 1.07442,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 75,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: 3,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SNOWY,
            ATTR_FORECAST_TIME: "2021-03-15T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 7.305040000000001,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 95,
            ATTR_FORECAST_TEMP: 1,
            ATTR_FORECAST_TEMP_LOW: 0,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-16T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0.00508,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 5,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: -2,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-17T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 11,
            ATTR_FORECAST_TEMP_LOW: 1,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-18T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 5,
            ATTR_FORECAST_TEMP: 12,
            ATTR_FORECAST_TEMP_LOW: 6,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-19T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0.1778,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 45,
            ATTR_FORECAST_TEMP: 9,
            ATTR_FORECAST_TEMP_LOW: 5,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_RAINY,
            ATTR_FORECAST_TIME: "2021-03-20T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 1.2319,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 55,
            ATTR_FORECAST_TEMP: 5,
            ATTR_FORECAST_TEMP_LOW: 3,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-21T00:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0.043179999999999996,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 20,
            ATTR_FORECAST_TEMP: 7,
            ATTR_FORECAST_TEMP_LOW: 1,
        },
    ]
    assert weather_state.attributes[ATTR_FRIENDLY_NAME] == "ClimaCell - Daily"
    assert weather_state.attributes[ATTR_WEATHER_HUMIDITY] == 24
    assert weather_state.attributes[ATTR_WEATHER_OZONE] == 52.625
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE] == 1028.124632345
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE] == 7
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY] == 9.994026240000002
    assert weather_state.attributes[ATTR_WEATHER_WIND_BEARING] == 320.31
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED] == 14.62893696
    assert weather_state.attributes[ATTR_CLOUD_COVER] == 1
    assert weather_state.attributes[ATTR_WIND_GUST] == 24.075786240000003
    assert weather_state.attributes[ATTR_PRECIPITATION_TYPE] == "rain"


async def test_v4_weather(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test v4 weather data."""
    weather_state = await _setup(hass, API_V4_ENTRY_DATA)
    assert weather_state.state == ATTR_CONDITION_SUNNY
    assert weather_state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert weather_state.attributes[ATTR_FORECAST] == [
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SUNNY,
            ATTR_FORECAST_TIME: "2021-03-07T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 8,
            ATTR_FORECAST_TEMP_LOW: -3,
            ATTR_FORECAST_WIND_BEARING: 239.6,
            ATTR_FORECAST_WIND_SPEED: 15.272674560000002,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-08T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 10,
            ATTR_FORECAST_TEMP_LOW: -3,
            ATTR_FORECAST_WIND_BEARING: 262.82,
            ATTR_FORECAST_WIND_SPEED: 11.65165056,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-09T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 19,
            ATTR_FORECAST_TEMP_LOW: 0,
            ATTR_FORECAST_WIND_BEARING: 229.3,
            ATTR_FORECAST_WIND_SPEED: 11.3458752,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-10T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 18,
            ATTR_FORECAST_TEMP_LOW: 3,
            ATTR_FORECAST_WIND_BEARING: 149.91,
            ATTR_FORECAST_WIND_SPEED: 17.123420160000002,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-11T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 19,
            ATTR_FORECAST_TEMP_LOW: 9,
            ATTR_FORECAST_WIND_BEARING: 210.45,
            ATTR_FORECAST_WIND_SPEED: 25.250607360000004,
        },
        {
            ATTR_FORECAST_CONDITION: "rainy",
            ATTR_FORECAST_TIME: "2021-03-12T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0.12192000000000001,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 20,
            ATTR_FORECAST_TEMP_LOW: 12,
            ATTR_FORECAST_WIND_BEARING: 217.98,
            ATTR_FORECAST_WIND_SPEED: 19.794931200000004,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-13T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 12,
            ATTR_FORECAST_TEMP_LOW: 6,
            ATTR_FORECAST_WIND_BEARING: 58.79,
            ATTR_FORECAST_WIND_SPEED: 15.642823680000001,
        },
        {
            ATTR_FORECAST_CONDITION: "snowy",
            ATTR_FORECAST_TIME: "2021-03-14T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 23.95728,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 95,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: 1,
            ATTR_FORECAST_WIND_BEARING: 70.25,
            ATTR_FORECAST_WIND_SPEED: 26.15184,
        },
        {
            ATTR_FORECAST_CONDITION: "snowy",
            ATTR_FORECAST_TIME: "2021-03-15T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 1.46304,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 55,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: -1,
            ATTR_FORECAST_WIND_BEARING: 84.47,
            ATTR_FORECAST_WIND_SPEED: 25.57247616,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-16T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: -2,
            ATTR_FORECAST_WIND_BEARING: 103.85,
            ATTR_FORECAST_WIND_SPEED: 10.79869824,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-17T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 11,
            ATTR_FORECAST_TEMP_LOW: 1,
            ATTR_FORECAST_WIND_BEARING: 145.41,
            ATTR_FORECAST_WIND_SPEED: 11.69993088,
        },
        {
            ATTR_FORECAST_CONDITION: "cloudy",
            ATTR_FORECAST_TIME: "2021-03-18T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 10,
            ATTR_FORECAST_TEMP: 12,
            ATTR_FORECAST_TEMP_LOW: 5,
            ATTR_FORECAST_WIND_BEARING: 62.99,
            ATTR_FORECAST_WIND_SPEED: 10.58948352,
        },
        {
            ATTR_FORECAST_CONDITION: "rainy",
            ATTR_FORECAST_TIME: "2021-03-19T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 2.92608,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 55,
            ATTR_FORECAST_TEMP: 9,
            ATTR_FORECAST_TEMP_LOW: 4,
            ATTR_FORECAST_WIND_BEARING: 68.54,
            ATTR_FORECAST_WIND_SPEED: 22.38597504,
        },
        {
            ATTR_FORECAST_CONDITION: "snowy",
            ATTR_FORECAST_TIME: "2021-03-20T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 1.2192,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 33.3,
            ATTR_FORECAST_TEMP: 5,
            ATTR_FORECAST_TEMP_LOW: 2,
            ATTR_FORECAST_WIND_BEARING: 56.98,
            ATTR_FORECAST_WIND_SPEED: 27.922118400000002,
        },
    ]
    assert weather_state.attributes[ATTR_FRIENDLY_NAME] == "ClimaCell - Daily"
    assert weather_state.attributes[ATTR_WEATHER_HUMIDITY] == 23
    assert weather_state.attributes[ATTR_WEATHER_OZONE] == 46.53
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE] == 1027.7690615000001
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE] == 7
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY] == 13.116153600000002
    assert weather_state.attributes[ATTR_WEATHER_WIND_BEARING] == 315.14
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED] == 15.01517952
    assert weather_state.attributes[ATTR_CLOUD_COVER] == 1
    assert weather_state.attributes[ATTR_WIND_GUST] == 20.34210816
    assert weather_state.attributes[ATTR_PRECIPITATION_TYPE] == "rain"
