"""Tests for the sensors provided by the Ambee integration."""
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

from tests.common import MockConfigEntry


async def test_air_quality(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Ambee Air Quality sensors."""
    state = hass.states.get("sensor.particulate_matter_2_5_mm")
    assert state
    assert state.state == "3.14"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Particulate Matter < 2.5 μm"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.particulate_matter_10_mm")
    assert state
    assert state.state == "5.24"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Particulate Matter < 10 μm"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.sulphur_dioxide_so2")
    assert state
    assert state.state == "0.031"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sulphur Dioxide (SO2)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.nitrogen_dioxide_no2")
    assert state
    assert state.state == "0.66"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Nitrogen Dioxide (NO2)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.ozone")
    assert state
    assert state.state == "17.067"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Ozone"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.carbon_monoxide_co")
    assert state
    assert state.state == "0.105"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_CO
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Carbon Monoxide (CO)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_MILLION
    )

    state = hass.states.get("sensor.air_quality_index_aqi")
    assert state
    assert state.state == "13"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Air Quality Index (AQI)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
