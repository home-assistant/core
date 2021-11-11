"""The test for weather entity."""
import pytest
from pytest import approx

from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
)
from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PRESSURE_INHG,
    PRESSURE_PA,
    PRESSURE_PSI,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM


@pytest.mark.parametrize(
    "unit_system,native_unit,native_value,state_unit",
    [
        (IMPERIAL_SYSTEM, TEMP_FAHRENHEIT, 100, TEMP_FAHRENHEIT),
        (IMPERIAL_SYSTEM, TEMP_CELSIUS, 38, TEMP_FAHRENHEIT),
        (METRIC_SYSTEM, TEMP_FAHRENHEIT, 100, TEMP_CELSIUS),
        (METRIC_SYSTEM, TEMP_CELSIUS, 38, TEMP_CELSIUS),
    ],
)
async def test_temperature_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    native_value,
    state_unit,
):
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            native_temperature=native_value,
            native_temperature_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        convert_temperature(native_value, native_unit, state_unit), rel=0.1
    )


@pytest.mark.parametrize(
    "unit_system,native_unit,native_value,state_unit",
    [
        (IMPERIAL_SYSTEM, PRESSURE_INHG, 30, PRESSURE_PSI),
        (METRIC_SYSTEM, PRESSURE_INHG, 30, PRESSURE_PA),
    ],
)
async def test_pressure_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    native_value,
    state_unit,
):
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            native_temperature=None,
            native_temperature_unit=None,
            native_pressure=native_value,
            native_pressure_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(
        convert_pressure(native_value, native_unit, state_unit)
    )


@pytest.mark.parametrize(
    "unit_system,native_unit,native_value,state_unit",
    [
        (IMPERIAL_SYSTEM, LENGTH_MILES, 30, LENGTH_MILES),
        (IMPERIAL_SYSTEM, LENGTH_KILOMETERS, 30, LENGTH_MILES),
        (METRIC_SYSTEM, LENGTH_KILOMETERS, 30, LENGTH_KILOMETERS),
        (METRIC_SYSTEM, LENGTH_MILES, 30, LENGTH_KILOMETERS),
    ],
)
async def test_visibility_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    native_value,
    state_unit,
):
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            native_temperature=None,
            native_temperature_unit=None,
            native_visibility=native_value,
            native_visibility_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == approx(
        convert_distance(native_value, native_unit, state_unit)
    )
