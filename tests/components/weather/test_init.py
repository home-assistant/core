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
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.speed import convert as convert_speed
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM, UnitSystem

from tests.testing_config.custom_components.test import weather as WeatherPlatform


async def create_entity(hass: HomeAssistant, **kwargs):
    """Create the weather entity to run tests on."""
    kwargs = {"native_temperature": None, "native_temperature_unit": None, **kwargs}
    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeatherMockForecast(
            name="Test", condition=ATTR_CONDITION_SUNNY, **kwargs
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()
    return entity0


@pytest.mark.parametrize("unit_system", [IMPERIAL_SYSTEM, METRIC_SYSTEM])
async def test_temperature_conversion(
    hass: HomeAssistant, enable_custom_integrations, unit_system: UnitSystem
):
    """Test temperature conversion."""
    hass.config.units = unit_system
    native_value = 38
    native_unit = TEMP_FAHRENHEIT

    entity0 = await create_entity(
        hass, native_temperature=native_value, native_temperature_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_temperature(native_value, native_unit, TEMP_FAHRENHEIT)
    if unit_system == METRIC_SYSTEM:
        expected = convert_temperature(native_value, native_unit, TEMP_CELSIUS)
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        expected, rel=0.1
    )
    assert float(forecast[ATTR_FORECAST_TEMP]) == approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_TEMP_LOW]) == approx(expected, rel=0.1)


@pytest.mark.parametrize("unit_system", [IMPERIAL_SYSTEM, METRIC_SYSTEM])
async def test_pressure_conversion(
    hass: HomeAssistant, enable_custom_integrations, unit_system: UnitSystem
):
    """Test pressure conversion."""
    hass.config.units = unit_system
    native_value = 30
    native_unit = PRESSURE_INHG

    entity0 = await create_entity(
        hass, native_pressure=native_value, native_pressure_unit=native_unit
    )
    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_pressure(native_value, native_unit, PRESSURE_INHG)
    if unit_system == METRIC_SYSTEM:
        expected = convert_pressure(native_value, native_unit, PRESSURE_HPA)
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(expected, rel=1e-2)
    assert float(forecast[ATTR_FORECAST_PRESSURE]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("unit_system", [IMPERIAL_SYSTEM, METRIC_SYSTEM])
async def test_wind_speed_conversion(
    hass: HomeAssistant, enable_custom_integrations, unit_system: UnitSystem
):
    """Test wind speed conversion."""
    hass.config.units = unit_system
    native_value = 10
    native_unit = SPEED_METERS_PER_SECOND

    entity0 = await create_entity(
        hass, native_wind_speed=native_value, native_wind_speed_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_speed(native_value, native_unit, SPEED_MILES_PER_HOUR)
    if unit_system == METRIC_SYSTEM:
        expected = convert_speed(native_value, native_unit, SPEED_METERS_PER_SECOND)
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_WIND_SPEED]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("unit_system", [IMPERIAL_SYSTEM, METRIC_SYSTEM])
async def test_visibility_conversion(
    hass: HomeAssistant, enable_custom_integrations, unit_system: UnitSystem
):
    """Test visibility conversion."""
    hass.config.units = unit_system
    native_value = 10
    native_unit = LENGTH_MILES

    entity0 = await create_entity(
        hass, native_visibility=native_value, native_visibility_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    expected = convert_distance(native_value, native_unit, LENGTH_MILES)
    if unit_system == METRIC_SYSTEM:
        expected = convert_distance(native_value, native_unit, LENGTH_KILOMETERS)
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("unit_system", [IMPERIAL_SYSTEM, METRIC_SYSTEM])
async def test_precipitation_conversion(
    hass: HomeAssistant, enable_custom_integrations, unit_system: UnitSystem
):
    """Test precipitation conversion."""
    hass.config.units = unit_system
    native_value = 30
    native_unit = LENGTH_MILLIMETERS

    entity0 = await create_entity(
        hass, native_precipitation=native_value, native_precipitation_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = convert_distance(native_value, native_unit, LENGTH_INCHES)
    if unit_system == METRIC_SYSTEM:
        expected = convert_distance(native_value, native_unit, LENGTH_MILLIMETERS)
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == approx(expected, rel=1e-2)


async def test_none_forecast(
    hass: HomeAssistant,
    enable_custom_integrations,
):
    """Test that conversion with None values succeeds."""
    entity0 = await create_entity(
        hass,
        native_pressure=None,
        native_pressure_unit=PRESSURE_INHG,
        native_wind_speed=None,
        native_wind_speed_unit=SPEED_METERS_PER_SECOND,
        native_precipitation=None,
        native_precipitation_unit=LENGTH_MILLIMETERS,
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    assert forecast[ATTR_FORECAST_PRESSURE] is None
    assert forecast[ATTR_FORECAST_WIND_SPEED] is None
    assert forecast[ATTR_FORECAST_PRECIPITATION] is None


async def test_custom_units(hass: HomeAssistant, enable_custom_integrations) -> None:
    """Test custom unit."""
    native_value = 5
    native_unit = SPEED_METERS_PER_SECOND
    custom_unit = SPEED_MILES_PER_HOUR

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get_or_create("weather", "test", "very_unique")
    entity_registry.async_update_entity_options(
        entry.entity_id, "weather", {"wind_speed_unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            condition=ATTR_CONDITION_SUNNY,
            native_temperature=None,
            native_temperature_unit=None,
            native_wind_speed=native_value,
            native_wind_speed_unit=native_unit,
            unique_id="very_unique",
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    expected = convert_speed(native_value, native_unit, SPEED_MILES_PER_HOUR)
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(
        expected, rel=1e-2
    )
