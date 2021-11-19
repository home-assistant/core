"""The test for weather entity."""
import pytest
from pytest import approx

from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRESSURE,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.const import (
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PRESSURE_INHG,
    PRESSURE_PA,
    PRESSURE_PSI,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.speed import convert as convert_speed
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
            temperature=native_value,
            temperature_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
            forecast=[
                {
                    ATTR_FORECAST_TEMP: native_value,
                    ATTR_FORECAST_TEMP_LOW: native_value,
                }
            ],
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_temperature(native_value, native_unit, state_unit)
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        expected, rel=0.1
    )
    assert float(forecast[ATTR_FORECAST_TEMP]) == approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_TEMP_LOW]) == approx(expected, rel=0.1)


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
    """Test pressure conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            temperature=None,
            temperature_unit=None,
            pressure=native_value,
            pressure_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
            forecast=[
                {
                    ATTR_FORECAST_TEMP: None,
                    ATTR_FORECAST_PRESSURE: native_value,
                }
            ],
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_pressure(native_value, native_unit, state_unit)
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(expected)
    assert float(forecast[ATTR_FORECAST_PRESSURE]) == approx(expected)


@pytest.mark.parametrize(
    "unit_system,native_unit,native_value,state_unit",
    [
        (IMPERIAL_SYSTEM, SPEED_METERS_PER_SECOND, 30, SPEED_MILES_PER_HOUR),
        (METRIC_SYSTEM, SPEED_MILES_PER_HOUR, 30, SPEED_METERS_PER_SECOND),
    ],
)
async def test_wind_speed_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    native_value,
    state_unit,
):
    """Test wind speed conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            temperature=None,
            temperature_unit=None,
            wind_speed=native_value,
            wind_speed_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
            forecast=[
                {
                    ATTR_FORECAST_TEMP: None,
                    ATTR_FORECAST_WIND_SPEED: native_value,
                }
            ],
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_speed(native_value, native_unit, state_unit)
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(expected)
    assert float(forecast[ATTR_FORECAST_WIND_SPEED]) == approx(expected)


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
    """Test visibility conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            temperature=None,
            temperature_unit=None,
            visibility=native_value,
            visibility_unit=native_unit,
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


@pytest.mark.parametrize(
    "unit_system,native_unit,native_value,state_unit",
    [
        (IMPERIAL_SYSTEM, LENGTH_MILLIMETERS, 30, LENGTH_INCHES),
        (METRIC_SYSTEM, LENGTH_INCHES, 30, LENGTH_MILLIMETERS),
    ],
)
async def test_precipitation_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    native_value,
    state_unit,
):
    """Test precipitation conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            temperature=None,
            temperature_unit=None,
            precipitation_unit=native_unit,
            condition=ATTR_CONDITION_SUNNY,
            forecast=[
                {
                    ATTR_FORECAST_TEMP: None,
                    ATTR_FORECAST_PRECIPITATION: native_value,
                }
            ],
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_distance(native_value, native_unit, state_unit)
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == approx(expected)
