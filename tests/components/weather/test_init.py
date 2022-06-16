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
    ROUNDING_PRECISION,
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


@pytest.mark.parametrize("unit", [TEMP_FAHRENHEIT, TEMP_CELSIUS])
async def test_temperature(hass: HomeAssistant, enable_custom_integrations, unit: str):
    """Test temperature."""
    native_value = 38
    native_unit = unit

    entity0 = await create_entity(
        hass, native_temperature=native_value, native_temperature_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = native_value
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        expected, rel=0.1
    )
    assert float(forecast[ATTR_FORECAST_TEMP]) == approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_TEMP_LOW]) == approx(expected, rel=0.1)


@pytest.mark.parametrize("unit", [PRESSURE_INHG, PRESSURE_HPA])
async def test_pressure(hass: HomeAssistant, enable_custom_integrations, unit: str):
    """Test pressure."""
    native_value = 30
    native_unit = unit

    entity0 = await create_entity(
        hass, native_pressure=native_value, native_pressure_unit=native_unit
    )
    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = native_value
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(expected, rel=1e-2)
    assert float(forecast[ATTR_FORECAST_PRESSURE]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("unit", [SPEED_MILES_PER_HOUR, SPEED_METERS_PER_SECOND])
async def test_wind_speed(hass: HomeAssistant, enable_custom_integrations, unit: str):
    """Test wind speed."""
    native_value = 10
    native_unit = unit

    entity0 = await create_entity(
        hass, native_wind_speed=native_value, native_wind_speed_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = native_value
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_WIND_SPEED]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("unit", [LENGTH_KILOMETERS, LENGTH_MILES])
async def test_visibility(hass: HomeAssistant, enable_custom_integrations, unit: str):
    """Test visibility."""
    native_value = 10
    native_unit = unit

    entity0 = await create_entity(
        hass, native_visibility=native_value, native_visibility_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    expected = native_value
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("unit", [LENGTH_INCHES, LENGTH_MILLIMETERS])
async def test_precipitation(
    hass: HomeAssistant, enable_custom_integrations, unit: str
):
    """Test precipitation."""
    native_value = 30
    native_unit = unit

    entity0 = await create_entity(
        hass, native_precipitation=native_value, native_precipitation_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = native_value
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
    wind_speed_value = 5
    wind_speed_unit = SPEED_METERS_PER_SECOND
    pressure_value = 110
    pressure_unit = PRESSURE_HPA
    temperature_value = 20
    temperature_unit = TEMP_CELSIUS
    visibility_value = 11
    visibility_unit = LENGTH_KILOMETERS

    set_options = {
        "wind_speed_unit_of_measurement": SPEED_MILES_PER_HOUR,
        "precipitation_unit_of_measurement": LENGTH_INCHES,
        "pressure_unit_of_measurement": PRESSURE_INHG,
        "temperature_unit_of_measurement": TEMP_FAHRENHEIT,
        "visibility_unit_of_measurement": LENGTH_MILES,
    }

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get_or_create("weather", "test", "very_unique")
    entity_registry.async_update_entity_options(entry.entity_id, "weather", set_options)
    await hass.async_block_till_done()

    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeather(
            name="Test",
            condition=ATTR_CONDITION_SUNNY,
            native_temperature=temperature_value,
            native_temperature_unit=temperature_unit,
            native_wind_speed=wind_speed_value,
            native_wind_speed_unit=wind_speed_unit,
            native_pressure=pressure_value,
            native_pressure_unit=pressure_unit,
            native_visibility=visibility_value,
            native_visibility_unit=visibility_unit,
            unique_id="very_unique",
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    expected_wind_speed = round(
        convert_speed(wind_speed_value, wind_speed_unit, SPEED_MILES_PER_HOUR),
        ROUNDING_PRECISION,
    )
    expected_temperature = convert_temperature(
        temperature_value, temperature_unit, TEMP_FAHRENHEIT
    )
    expected_pressure = round(
        convert_pressure(pressure_value, pressure_unit, PRESSURE_INHG),
        ROUNDING_PRECISION,
    )
    expected_visibility = round(
        convert_distance(visibility_value, visibility_unit, LENGTH_MILES),
        ROUNDING_PRECISION,
    )

    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(
        expected_wind_speed
    )
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        expected_temperature, rel=0.1
    )
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(expected_pressure)
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == approx(
        expected_visibility
    )
