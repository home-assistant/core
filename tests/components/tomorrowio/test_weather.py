"""Tests for Tomorrow.io weather entity."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from freezegun import freeze_time

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
    ATTR_WEATHER_PRECIPITATION_UNIT,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_PRESSURE_UNIT,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_VISIBILITY_UNIT,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_WIND_SPEED_UNIT,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, SOURCE_USER
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_FRIENDLY_NAME, CONF_NAME
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from .const import API_V4_ENTRY_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


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
    with freeze_time(
        datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC)
    ) as frozen_time:
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
        # the enabled entity state will be fired in RELOAD_AFTER_UPDATE_DELAY
        frozen_time.tick(delta=RELOAD_AFTER_UPDATE_DELAY)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 3

    return hass.states.get("weather.tomorrow_io_daily")


async def test_v4_weather(hass: HomeAssistant) -> None:
    """Test v4 weather data."""
    weather_state = await _setup(hass, API_V4_ENTRY_DATA)
    assert weather_state.state == ATTR_CONDITION_SUNNY
    assert weather_state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert len(weather_state.attributes[ATTR_FORECAST]) == 14
    assert weather_state.attributes[ATTR_FORECAST][0] == {
        ATTR_FORECAST_CONDITION: ATTR_CONDITION_SUNNY,
        ATTR_FORECAST_TIME: "2021-03-07T11:00:00+00:00",
        ATTR_FORECAST_PRECIPITATION: 0,
        ATTR_FORECAST_PRECIPITATION_PROBABILITY: 0,
        ATTR_FORECAST_TEMP: 45.9,
        ATTR_FORECAST_TEMP_LOW: 26.1,
        ATTR_FORECAST_WIND_BEARING: 239.6,
        ATTR_FORECAST_WIND_SPEED: 34.16,  # 9.49 m/s -> km/h
    }
    assert weather_state.attributes[ATTR_FRIENDLY_NAME] == "Tomorrow.io - Daily"
    assert weather_state.attributes[ATTR_WEATHER_HUMIDITY] == 23
    assert weather_state.attributes[ATTR_WEATHER_OZONE] == 46.53
    assert weather_state.attributes[ATTR_WEATHER_PRECIPITATION_UNIT] == "mm"
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE] == 30.35
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE_UNIT] == "hPa"
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE] == 44.1
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == "°C"
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY] == 8.15
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == "km"
    assert weather_state.attributes[ATTR_WEATHER_WIND_BEARING] == 315.14
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED] == 33.59  # 9.33 m/s ->km/h
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED_UNIT] == "km/h"
