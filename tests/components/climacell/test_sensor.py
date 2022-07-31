"""Tests for Climacell sensor entities."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.climacell.const import ATTRIBUTION, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from .const import API_V3_ENTRY_DATA

from tests.common import MockConfigEntry

CC_SENSOR_ENTITY_ID = "sensor.climacell_{}"

O3 = "ozone"
CO = "carbon_monoxide"
NO2 = "nitrogen_dioxide"
SO2 = "sulfur_dioxide"
PM25 = "particulate_matter_2_5_mm"
PM10 = "particulate_matter_10_mm"
MEP_AQI = "china_mep_air_quality_index"
MEP_HEALTH_CONCERN = "china_mep_health_concern"
MEP_PRIMARY_POLLUTANT = "china_mep_primary_pollutant"
EPA_AQI = "us_epa_air_quality_index"
EPA_HEALTH_CONCERN = "us_epa_health_concern"
EPA_PRIMARY_POLLUTANT = "us_epa_primary_pollutant"
FIRE_INDEX = "fire_index"
GRASS_POLLEN = "grass_pollen_index"
WEED_POLLEN = "weed_pollen_index"
TREE_POLLEN = "tree_pollen_index"
FEELS_LIKE = "feels_like"
DEW_POINT = "dew_point"
PRESSURE_SURFACE_LEVEL = "pressure_surface_level"
SNOW_ACCUMULATION = "snow_accumulation"
ICE_ACCUMULATION = "ice_accumulation"
GHI = "global_horizontal_irradiance"
CLOUD_BASE = "cloud_base"
CLOUD_COVER = "cloud_cover"
CLOUD_CEILING = "cloud_ceiling"
WIND_GUST = "wind_gust"
PRECIPITATION_TYPE = "precipitation_type"

V3_FIELDS = [
    O3,
    CO,
    NO2,
    SO2,
    PM25,
    PM10,
    MEP_AQI,
    MEP_HEALTH_CONCERN,
    MEP_PRIMARY_POLLUTANT,
    EPA_AQI,
    EPA_HEALTH_CONCERN,
    EPA_PRIMARY_POLLUTANT,
    FIRE_INDEX,
    GRASS_POLLEN,
    WEED_POLLEN,
    TREE_POLLEN,
]

V4_FIELDS = [
    *V3_FIELDS,
    FEELS_LIKE,
    DEW_POINT,
    PRESSURE_SURFACE_LEVEL,
    GHI,
    CLOUD_BASE,
    CLOUD_COVER,
    CLOUD_CEILING,
    WIND_GUST,
    PRECIPITATION_TYPE,
]


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


async def _setup(
    hass: HomeAssistant, sensors: list[str], config: dict[str, Any]
) -> State:
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
        for entity_name in sensors:
            _enable_entity(hass, CC_SENSOR_ENTITY_ID.format(entity_name))
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == len(sensors)


def check_sensor_state(hass: HomeAssistant, entity_name: str, value: str):
    """Check the state of a ClimaCell sensor."""
    state = hass.states.get(CC_SENSOR_ENTITY_ID.format(entity_name))
    assert state
    assert state.state == value
    assert state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION


async def test_v3_sensor(
    hass: HomeAssistant,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test v3 sensor data."""
    await _setup(hass, V3_FIELDS, API_V3_ENTRY_DATA)
    check_sensor_state(hass, O3, "52.625")
    check_sensor_state(hass, CO, "0.875")
    check_sensor_state(hass, NO2, "14.1875")
    check_sensor_state(hass, SO2, "2")
    check_sensor_state(hass, PM25, "5.3125")
    check_sensor_state(hass, PM10, "27")
    check_sensor_state(hass, MEP_AQI, "27")
    check_sensor_state(hass, MEP_HEALTH_CONCERN, "Good")
    check_sensor_state(hass, MEP_PRIMARY_POLLUTANT, "pm10")
    check_sensor_state(hass, EPA_AQI, "22.3125")
    check_sensor_state(hass, EPA_HEALTH_CONCERN, "Good")
    check_sensor_state(hass, EPA_PRIMARY_POLLUTANT, "pm25")
    check_sensor_state(hass, FIRE_INDEX, "9")
    check_sensor_state(hass, GRASS_POLLEN, "minimal_to_none")
    check_sensor_state(hass, WEED_POLLEN, "minimal_to_none")
    check_sensor_state(hass, TREE_POLLEN, "minimal_to_none")
