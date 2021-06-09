"""Tests for the sensors provided by the Ambee integration."""
from homeassistant.components.ambee.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_air_quality(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Ambee Air Quality sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.particulate_matter_2_5_mm")
    entry = entity_registry.async_get("sensor.particulate_matter_2_5_mm")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_particulate_matter_2_5"
    assert state.state == "3.14"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Particulate Matter < 2.5 μm"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.particulate_matter_10_mm")
    entry = entity_registry.async_get("sensor.particulate_matter_10_mm")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_particulate_matter_10"
    assert state.state == "5.24"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Particulate Matter < 10 μm"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.sulphur_dioxide_so2")
    entry = entity_registry.async_get("sensor.sulphur_dioxide_so2")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_sulphur_dioxide"
    assert state.state == "0.031"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sulphur Dioxide (SO2)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.nitrogen_dioxide_no2")
    entry = entity_registry.async_get("sensor.nitrogen_dioxide_no2")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_nitrogen_dioxide"
    assert state.state == "0.66"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Nitrogen Dioxide (NO2)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.ozone")
    entry = entity_registry.async_get("sensor.ozone")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_ozone"
    assert state.state == "17.067"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Ozone"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.carbon_monoxide_co")
    entry = entity_registry.async_get("sensor.carbon_monoxide_co")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_carbon_monoxide"
    assert state.state == "0.105"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_CO
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Carbon Monoxide (CO)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_MILLION
    )

    state = hass.states.get("sensor.air_quality_index_aqi")
    entry = entity_registry.async_get("sensor.air_quality_index_aqi")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_index"
    assert state.state == "13"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Air Quality Index (AQI)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_air_quality")}
    assert device_entry.manufacturer == "Ambee"
    assert device_entry.name == "Air Quality"
    assert not device_entry.model
    assert not device_entry.sw_version
