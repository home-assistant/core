"""Tests for Tomorrow.io weather entity."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.tomorrowio.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.tomorrowio.const import (
    ATTRIBUTION,
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
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
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_FRIENDLY_NAME, CONF_NAME
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from .const import API_V4_ENTRY_DATA

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
        data = _get_config_schema(hass, SOURCE_USER)(config)
        data[CONF_NAME] = DEFAULT_NAME
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=data,
            options={CONF_TIMESTEP: DEFAULT_TIMESTEP},
            unique_id=_get_unique_id(hass, data),
            version=1,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        for entity_name in ("hourly", "nowcast"):
            _enable_entity(hass, f"weather.tomorrow_io_{entity_name}")
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 3

    return hass.states.get("weather.tomorrow_io_daily")


async def test_v4_weather(
    hass: HomeAssistant,
    tomorrowio_config_entry_update: pytest.fixture,
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
            ATTR_FORECAST_WIND_SPEED: 4.24,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-08T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 10,
            ATTR_FORECAST_TEMP_LOW: -3,
            ATTR_FORECAST_WIND_BEARING: 262.82,
            ATTR_FORECAST_WIND_SPEED: 3.24,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-09T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 19,
            ATTR_FORECAST_TEMP_LOW: 0,
            ATTR_FORECAST_WIND_BEARING: 229.3,
            ATTR_FORECAST_WIND_SPEED: 3.15,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-10T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 18,
            ATTR_FORECAST_TEMP_LOW: 3,
            ATTR_FORECAST_WIND_BEARING: 149.91,
            ATTR_FORECAST_WIND_SPEED: 4.76,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-11T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 19,
            ATTR_FORECAST_TEMP_LOW: 9,
            ATTR_FORECAST_WIND_BEARING: 210.45,
            ATTR_FORECAST_WIND_SPEED: 7.01,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_RAINY,
            ATTR_FORECAST_TIME: "2021-03-12T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0.12,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 20,
            ATTR_FORECAST_TEMP_LOW: 12,
            ATTR_FORECAST_WIND_BEARING: 217.98,
            ATTR_FORECAST_WIND_SPEED: 5.5,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-13T11:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 25,
            ATTR_FORECAST_TEMP: 12,
            ATTR_FORECAST_TEMP_LOW: 6,
            ATTR_FORECAST_WIND_BEARING: 58.79,
            ATTR_FORECAST_WIND_SPEED: 4.35,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SNOWY,
            ATTR_FORECAST_TIME: "2021-03-14T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 23.96,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 95,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: 1,
            ATTR_FORECAST_WIND_BEARING: 70.25,
            ATTR_FORECAST_WIND_SPEED: 7.26,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SNOWY,
            ATTR_FORECAST_TIME: "2021-03-15T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 1.46,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 55,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: -1,
            ATTR_FORECAST_WIND_BEARING: 84.47,
            ATTR_FORECAST_WIND_SPEED: 7.1,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-16T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 6,
            ATTR_FORECAST_TEMP_LOW: -2,
            ATTR_FORECAST_WIND_BEARING: 103.85,
            ATTR_FORECAST_WIND_SPEED: 3.0,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-17T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
            ATTR_FORECAST_TEMP: 11,
            ATTR_FORECAST_TEMP_LOW: 1,
            ATTR_FORECAST_WIND_BEARING: 145.41,
            ATTR_FORECAST_WIND_SPEED: 3.25,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_CLOUDY,
            ATTR_FORECAST_TIME: "2021-03-18T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 0,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 10,
            ATTR_FORECAST_TEMP: 12,
            ATTR_FORECAST_TEMP_LOW: 5,
            ATTR_FORECAST_WIND_BEARING: 62.99,
            ATTR_FORECAST_WIND_SPEED: 2.94,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_RAINY,
            ATTR_FORECAST_TIME: "2021-03-19T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 2.93,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 55,
            ATTR_FORECAST_TEMP: 9,
            ATTR_FORECAST_TEMP_LOW: 4,
            ATTR_FORECAST_WIND_BEARING: 68.54,
            ATTR_FORECAST_WIND_SPEED: 6.22,
        },
        {
            ATTR_FORECAST_CONDITION: ATTR_CONDITION_SNOWY,
            ATTR_FORECAST_TIME: "2021-03-20T10:00:00+00:00",
            ATTR_FORECAST_PRECIPITATION: 1.22,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: 33.3,
            ATTR_FORECAST_TEMP: 5,
            ATTR_FORECAST_TEMP_LOW: 2,
            ATTR_FORECAST_WIND_BEARING: 56.98,
            ATTR_FORECAST_WIND_SPEED: 7.76,
        },
    ]
    assert weather_state.attributes[ATTR_FRIENDLY_NAME] == "Tomorrow.io - Daily"
    assert weather_state.attributes[ATTR_WEATHER_HUMIDITY] == 23
    assert weather_state.attributes[ATTR_WEATHER_OZONE] == 46.53
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE] == 102776.91
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE] == 7
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY] == 13.12
    assert weather_state.attributes[ATTR_WEATHER_WIND_BEARING] == 315.14
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED] == 4.17
