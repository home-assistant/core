"""The test for weather entity."""
from datetime import datetime

import pytest
from pytest import approx

from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRESSURE,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
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
    ROUNDING_PRECISION,
    Forecast,
    WeatherEntity,
    round_temperature,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_KILOMETERS_PER_HOUR,
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
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.testing_config.custom_components.test import weather as WeatherPlatform


class MockWeatherEntity(WeatherEntity):
    """Mock a Weather Entity."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_native_precipitation_unit = LENGTH_MILLIMETERS
        self._attr_native_pressure = 10
        self._attr_native_pressure_unit = PRESSURE_HPA
        self._attr_native_temperature = 20
        self._attr_native_temperature_unit = TEMP_CELSIUS
        self._attr_native_visibility = 30
        self._attr_native_visibility_unit = LENGTH_KILOMETERS
        self._attr_native_wind_speed = 3
        self._attr_native_wind_speed_unit = SPEED_METERS_PER_SECOND
        self._attr_forecast = [
            Forecast(
                datetime=datetime(2022, 6, 20, 20, 00, 00),
                native_precipitation=1,
                native_temperature=20,
            )
        ]


class MockWeatherEntityPrecision(WeatherEntity):
    """Mock a Weather Entity with precision."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_native_temperature = 20.3
        self._attr_native_temperature_unit = TEMP_CELSIUS
        self._attr_precision = PRECISION_HALVES


class MockWeatherEntityCompat(WeatherEntity):
    """Mock a Weather Entity using old attributes."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_precipitation_unit = LENGTH_MILLIMETERS
        self._attr_pressure = 10
        self._attr_pressure_unit = PRESSURE_HPA
        self._attr_temperature = 20
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_visibility = 30
        self._attr_visibility_unit = LENGTH_KILOMETERS
        self._attr_wind_speed = 3
        self._attr_wind_speed_unit = SPEED_METERS_PER_SECOND
        self._attr_forecast = [
            Forecast(
                datetime=datetime(2022, 6, 20, 20, 00, 00),
                precipitation=1,
                temperature=20,
            )
        ]


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


@pytest.mark.parametrize("native_unit", (TEMP_FAHRENHEIT, TEMP_CELSIUS))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    ((TEMP_CELSIUS, METRIC_SYSTEM), (TEMP_FAHRENHEIT, IMPERIAL_SYSTEM)),
)
async def test_temperature(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test temperature."""
    hass.config.units = unit_system
    native_value = 38
    state_value = convert_temperature(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_temperature=native_value, native_temperature_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        expected, rel=0.1
    )
    assert state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == state_unit
    assert float(forecast[ATTR_FORECAST_TEMP]) == approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_TEMP_LOW]) == approx(expected, rel=0.1)


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    ((TEMP_CELSIUS, METRIC_SYSTEM), (TEMP_FAHRENHEIT, IMPERIAL_SYSTEM)),
)
async def test_temperature_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test temperature when the entity does not declare a native unit."""
    hass.config.units = unit_system
    native_value = 38
    state_value = native_value

    entity0 = await create_entity(
        hass, native_temperature=native_value, native_temperature_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        expected, rel=0.1
    )
    assert state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == state_unit
    assert float(forecast[ATTR_FORECAST_TEMP]) == approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_TEMP_LOW]) == approx(expected, rel=0.1)


@pytest.mark.parametrize("native_unit", (PRESSURE_INHG, PRESSURE_INHG))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    ((PRESSURE_HPA, METRIC_SYSTEM), (PRESSURE_INHG, IMPERIAL_SYSTEM)),
)
async def test_pressure(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test pressure."""
    hass.config.units = unit_system
    native_value = 30
    state_value = convert_pressure(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_pressure=native_value, native_pressure_unit=native_unit
    )
    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(expected, rel=1e-2)
    assert float(forecast[ATTR_FORECAST_PRESSURE]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    ((PRESSURE_HPA, METRIC_SYSTEM), (PRESSURE_INHG, IMPERIAL_SYSTEM)),
)
async def test_pressure_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test pressure when the entity does not declare a native unit."""
    hass.config.units = unit_system
    native_value = 30
    state_value = native_value

    entity0 = await create_entity(
        hass, native_pressure=native_value, native_pressure_unit=native_unit
    )
    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(expected, rel=1e-2)
    assert float(forecast[ATTR_FORECAST_PRESSURE]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize(
    "native_unit",
    (SPEED_MILES_PER_HOUR, SPEED_KILOMETERS_PER_HOUR, SPEED_METERS_PER_SECOND),
)
@pytest.mark.parametrize(
    "state_unit, unit_system",
    (
        (SPEED_KILOMETERS_PER_HOUR, METRIC_SYSTEM),
        (SPEED_MILES_PER_HOUR, IMPERIAL_SYSTEM),
    ),
)
async def test_wind_speed(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test wind speed."""
    hass.config.units = unit_system
    native_value = 10
    state_value = convert_speed(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_wind_speed=native_value, native_wind_speed_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_WIND_SPEED]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    (
        (SPEED_KILOMETERS_PER_HOUR, METRIC_SYSTEM),
        (SPEED_MILES_PER_HOUR, IMPERIAL_SYSTEM),
    ),
)
async def test_wind_speed_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test wind speed when the entity does not declare a native unit."""
    hass.config.units = unit_system
    native_value = 10
    state_value = native_value

    entity0 = await create_entity(
        hass, native_wind_speed=native_value, native_wind_speed_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_WIND_SPEED]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("native_unit", (LENGTH_MILES, LENGTH_KILOMETERS))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    (
        (LENGTH_KILOMETERS, METRIC_SYSTEM),
        (LENGTH_MILES, IMPERIAL_SYSTEM),
    ),
)
async def test_visibility(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test visibility."""
    hass.config.units = unit_system
    native_value = 10
    state_value = convert_distance(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_visibility=native_value, native_visibility_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    (
        (LENGTH_KILOMETERS, METRIC_SYSTEM),
        (LENGTH_MILES, IMPERIAL_SYSTEM),
    ),
)
async def test_visibility_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test visibility when the entity does not declare a native unit."""
    hass.config.units = unit_system
    native_value = 10
    state_value = native_value

    entity0 = await create_entity(
        hass, native_visibility=native_value, native_visibility_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("native_unit", (LENGTH_INCHES, LENGTH_MILLIMETERS))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    (
        (LENGTH_MILLIMETERS, METRIC_SYSTEM),
        (LENGTH_INCHES, IMPERIAL_SYSTEM),
    ),
)
async def test_precipitation(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test precipitation."""
    hass.config.units = unit_system
    native_value = 30
    state_value = convert_distance(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_precipitation=native_value, native_precipitation_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == approx(expected, rel=1e-2)


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    "state_unit, unit_system",
    (
        (LENGTH_MILLIMETERS, METRIC_SYSTEM),
        (LENGTH_INCHES, IMPERIAL_SYSTEM),
    ),
)
async def test_precipitation_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations,
    native_unit: str,
    state_unit: str,
    unit_system,
):
    """Test precipitation when the entity does not declare a native unit."""
    hass.config.units = unit_system
    native_value = 30
    state_value = native_value

    entity0 = await create_entity(
        hass, native_precipitation=native_value, native_precipitation_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == approx(expected, rel=1e-2)


async def test_wind_bearing_and_ozone(
    hass: HomeAssistant,
    enable_custom_integrations,
):
    """Test wind bearing."""
    wind_bearing_value = 180
    ozone_value = 10

    entity0 = await create_entity(
        hass, wind_bearing=wind_bearing_value, ozone=ozone_value
    )

    state = hass.states.get(entity0.entity_id)
    assert float(state.attributes[ATTR_WEATHER_WIND_BEARING]) == 180
    assert float(state.attributes[ATTR_WEATHER_OZONE]) == 10


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

    assert forecast.get(ATTR_FORECAST_PRESSURE) is None
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) is None
    assert forecast.get(ATTR_FORECAST_PRECIPITATION) is None


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
    precipitation_value = 1.1
    precipitation_unit = LENGTH_MILLIMETERS

    set_options = {
        "wind_speed_unit": SPEED_MILES_PER_HOUR,
        "precipitation_unit": LENGTH_INCHES,
        "pressure_unit": PRESSURE_INHG,
        "temperature_unit": TEMP_FAHRENHEIT,
        "visibility_unit": LENGTH_MILES,
    }

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get_or_create("weather", "test", "very_unique")
    entity_registry.async_update_entity_options(entry.entity_id, "weather", set_options)
    await hass.async_block_till_done()

    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeatherMockForecast(
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
            native_precipitation=precipitation_value,
            native_precipitation_unit=precipitation_unit,
            unique_id="very_unique",
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

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
    expected_precipitation = round(
        convert_distance(precipitation_value, precipitation_unit, LENGTH_INCHES),
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
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == approx(
        expected_precipitation, rel=1e-2
    )

    assert (
        state.attributes[ATTR_WEATHER_PRECIPITATION_UNIT]
        == set_options["precipitation_unit"]
    )
    assert state.attributes[ATTR_WEATHER_PRESSURE_UNIT] == set_options["pressure_unit"]
    assert (
        state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT]
        == set_options["temperature_unit"]
    )
    assert (
        state.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == set_options["visibility_unit"]
    )
    assert (
        state.attributes[ATTR_WEATHER_WIND_SPEED_UNIT] == set_options["wind_speed_unit"]
    )


async def test_backwards_compatibility(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """Test backwards compatibility."""
    wind_speed_value = 5
    wind_speed_unit = SPEED_METERS_PER_SECOND
    pressure_value = 110000
    pressure_unit = PRESSURE_PA
    temperature_value = 20
    temperature_unit = TEMP_CELSIUS
    visibility_value = 11
    visibility_unit = LENGTH_KILOMETERS
    precipitation_value = 1
    precipitation_unit = LENGTH_MILLIMETERS

    hass.config.units = METRIC_SYSTEM

    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeatherMockForecastCompat(
            name="Test",
            condition=ATTR_CONDITION_SUNNY,
            temperature=temperature_value,
            temperature_unit=temperature_unit,
            wind_speed=wind_speed_value,
            wind_speed_unit=wind_speed_unit,
            pressure=pressure_value,
            pressure_unit=pressure_unit,
            visibility=visibility_value,
            visibility_unit=visibility_unit,
            precipitation=precipitation_value,
            precipitation_unit=precipitation_unit,
            unique_id="very_unique",
        )
    )
    platform.ENTITIES.append(
        platform.MockWeatherMockForecastCompat(
            name="Test2",
            condition=ATTR_CONDITION_SUNNY,
            temperature=temperature_value,
            temperature_unit=temperature_unit,
            wind_speed=wind_speed_value,
            pressure=pressure_value,
            visibility=visibility_value,
            precipitation=precipitation_value,
            unique_id="very_unique2",
        )
    )

    entity0 = platform.ENTITIES[0]
    entity1 = platform.ENTITIES[1]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test2"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]
    state1 = hass.states.get(entity1.entity_id)
    forecast1 = state1.attributes[ATTR_FORECAST][0]

    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(
        wind_speed_value * 3.6
    )
    assert state.attributes[ATTR_WEATHER_WIND_SPEED_UNIT] == SPEED_KILOMETERS_PER_HOUR
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        temperature_value, rel=0.1
    )
    assert state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == TEMP_CELSIUS
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == approx(
        pressure_value / 100
    )
    assert state.attributes[ATTR_WEATHER_PRESSURE_UNIT] == PRESSURE_HPA
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == approx(visibility_value)
    assert state.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == LENGTH_KILOMETERS
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == approx(
        precipitation_value, rel=1e-2
    )
    assert state.attributes[ATTR_WEATHER_PRECIPITATION_UNIT] == LENGTH_MILLIMETERS

    assert float(state1.attributes[ATTR_WEATHER_WIND_SPEED]) == approx(wind_speed_value)
    assert state1.attributes[ATTR_WEATHER_WIND_SPEED_UNIT] == SPEED_KILOMETERS_PER_HOUR
    assert float(state1.attributes[ATTR_WEATHER_TEMPERATURE]) == approx(
        temperature_value, rel=0.1
    )
    assert state1.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == TEMP_CELSIUS
    assert float(state1.attributes[ATTR_WEATHER_PRESSURE]) == approx(pressure_value)
    assert state1.attributes[ATTR_WEATHER_PRESSURE_UNIT] == PRESSURE_HPA
    assert float(state1.attributes[ATTR_WEATHER_VISIBILITY]) == approx(visibility_value)
    assert state1.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == LENGTH_KILOMETERS
    assert float(forecast1[ATTR_FORECAST_PRECIPITATION]) == approx(
        precipitation_value, rel=1e-2
    )
    assert state1.attributes[ATTR_WEATHER_PRECIPITATION_UNIT] == LENGTH_MILLIMETERS


async def test_backwards_compatibility_convert_values(
    hass: HomeAssistant, enable_custom_integrations
) -> None:
    """Test backward compatibility for converting values."""
    wind_speed_value = 5
    wind_speed_unit = SPEED_METERS_PER_SECOND
    pressure_value = 110000
    pressure_unit = PRESSURE_PA
    temperature_value = 20
    temperature_unit = TEMP_CELSIUS
    visibility_value = 11
    visibility_unit = LENGTH_KILOMETERS
    precipitation_value = 1
    precipitation_unit = LENGTH_MILLIMETERS

    hass.config.units = IMPERIAL_SYSTEM

    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeatherMockForecastCompat(
            name="Test",
            condition=ATTR_CONDITION_SUNNY,
            temperature=temperature_value,
            temperature_unit=temperature_unit,
            wind_speed=wind_speed_value,
            wind_speed_unit=wind_speed_unit,
            pressure=pressure_value,
            pressure_unit=pressure_unit,
            visibility=visibility_value,
            visibility_unit=visibility_unit,
            precipitation=precipitation_value,
            precipitation_unit=precipitation_unit,
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
    expected_precipitation = round(
        convert_distance(precipitation_value, precipitation_unit, LENGTH_INCHES),
        ROUNDING_PRECISION,
    )

    assert state.attributes == {
        ATTR_FORECAST: [
            {
                ATTR_FORECAST_PRECIPITATION: approx(expected_precipitation, rel=0.1),
                ATTR_FORECAST_PRESSURE: approx(expected_pressure, rel=0.1),
                ATTR_FORECAST_TEMP: approx(expected_temperature, rel=0.1),
                ATTR_FORECAST_TEMP_LOW: approx(expected_temperature, rel=0.1),
                ATTR_FORECAST_WIND_BEARING: None,
                ATTR_FORECAST_WIND_SPEED: approx(expected_wind_speed, rel=0.1),
            }
        ],
        ATTR_FRIENDLY_NAME: "Test",
        ATTR_WEATHER_PRECIPITATION_UNIT: LENGTH_INCHES,
        ATTR_WEATHER_PRESSURE: approx(expected_pressure, rel=0.1),
        ATTR_WEATHER_PRESSURE_UNIT: PRESSURE_INHG,
        ATTR_WEATHER_TEMPERATURE: approx(expected_temperature, rel=0.1),
        ATTR_WEATHER_TEMPERATURE_UNIT: TEMP_FAHRENHEIT,
        ATTR_WEATHER_VISIBILITY: approx(expected_visibility, rel=0.1),
        ATTR_WEATHER_VISIBILITY_UNIT: LENGTH_MILES,
        ATTR_WEATHER_WIND_SPEED: approx(expected_wind_speed, rel=0.1),
        ATTR_WEATHER_WIND_SPEED_UNIT: SPEED_MILES_PER_HOUR,
    }


async def test_backwards_compatibility_round_temperature(hass: HomeAssistant) -> None:
    """Test backward compatibility for rounding temperature."""

    assert round_temperature(20.3, PRECISION_HALVES) == 20.5
    assert round_temperature(20.3, PRECISION_TENTHS) == 20.3
    assert round_temperature(20.3, PRECISION_WHOLE) == 20
    assert round_temperature(None, PRECISION_WHOLE) is None


async def test_attr(hass: HomeAssistant) -> None:
    """Test the _attr attributes."""

    weather = MockWeatherEntity()
    weather.hass = hass

    assert weather.condition == ATTR_CONDITION_SUNNY
    assert weather.native_precipitation_unit == LENGTH_MILLIMETERS
    assert weather._precipitation_unit == LENGTH_MILLIMETERS
    assert weather.native_pressure == 10
    assert weather.native_pressure_unit == PRESSURE_HPA
    assert weather._pressure_unit == PRESSURE_HPA
    assert weather.native_temperature == 20
    assert weather.native_temperature_unit == TEMP_CELSIUS
    assert weather._temperature_unit == TEMP_CELSIUS
    assert weather.native_visibility == 30
    assert weather.native_visibility_unit == LENGTH_KILOMETERS
    assert weather._visibility_unit == LENGTH_KILOMETERS
    assert weather.native_wind_speed == 3
    assert weather.native_wind_speed_unit == SPEED_METERS_PER_SECOND
    assert weather._wind_speed_unit == SPEED_KILOMETERS_PER_HOUR


async def test_attr_compatibility(hass: HomeAssistant) -> None:
    """Test the _attr attributes in compatibility mode."""

    weather = MockWeatherEntityCompat()
    weather.hass = hass

    assert weather.condition == ATTR_CONDITION_SUNNY
    assert weather._precipitation_unit == LENGTH_MILLIMETERS
    assert weather.pressure == 10
    assert weather._pressure_unit == PRESSURE_HPA
    assert weather.temperature == 20
    assert weather._temperature_unit == TEMP_CELSIUS
    assert weather.visibility == 30
    assert weather.visibility_unit == LENGTH_KILOMETERS
    assert weather.wind_speed == 3
    assert weather._wind_speed_unit == SPEED_KILOMETERS_PER_HOUR

    forecast_entry = [
        Forecast(
            datetime=datetime(2022, 6, 20, 20, 00, 00),
            precipitation=1,
            temperature=20,
        )
    ]

    assert weather.forecast == forecast_entry

    assert weather.state_attributes == {
        ATTR_FORECAST: forecast_entry,
        ATTR_WEATHER_PRESSURE: 10.0,
        ATTR_WEATHER_PRESSURE_UNIT: PRESSURE_HPA,
        ATTR_WEATHER_TEMPERATURE: 20.0,
        ATTR_WEATHER_TEMPERATURE_UNIT: TEMP_CELSIUS,
        ATTR_WEATHER_VISIBILITY: 30.0,
        ATTR_WEATHER_VISIBILITY_UNIT: LENGTH_KILOMETERS,
        ATTR_WEATHER_WIND_SPEED: 3.0 * 3.6,
        ATTR_WEATHER_WIND_SPEED_UNIT: SPEED_KILOMETERS_PER_HOUR,
        ATTR_WEATHER_PRECIPITATION_UNIT: LENGTH_MILLIMETERS,
    }


async def test_precision_for_temperature(hass: HomeAssistant) -> None:
    """Test the precision for temperature."""

    weather = MockWeatherEntityPrecision()
    weather.hass = hass

    assert weather.condition == ATTR_CONDITION_SUNNY
    assert weather.native_temperature == 20.3
    assert weather._temperature_unit == TEMP_CELSIUS
    assert weather.precision == PRECISION_HALVES

    assert weather.state_attributes[ATTR_WEATHER_TEMPERATURE] == 20.5
