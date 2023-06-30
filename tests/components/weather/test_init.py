"""The test for weather entity."""
from datetime import datetime

import pytest

from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST,
    ATTR_FORECAST_APPARENT_TEMP,
    ATTR_FORECAST_DEW_POINT,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRESSURE,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_GUST_SPEED,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRECIPITATION_UNIT,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_PRESSURE_UNIT,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_VISIBILITY_UNIT,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_WIND_SPEED_UNIT,
    ROUNDING_PRECISION,
    Forecast,
    WeatherEntity,
    round_temperature,
)
from homeassistant.components.weather.const import (
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from tests.testing_config.custom_components.test import weather as WeatherPlatform


class MockWeatherEntity(WeatherEntity):
    """Mock a Weather Entity."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_native_precipitation_unit = UnitOfLength.MILLIMETERS
        self._attr_native_pressure = 10
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_native_temperature = 20
        self._attr_native_apparent_temperature = 25
        self._attr_native_dew_point = 2
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_visibility = 30
        self._attr_native_visibility_unit = UnitOfLength.KILOMETERS
        self._attr_native_wind_gust_speed = 10
        self._attr_native_wind_speed = 3
        self._attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
        self._attr_forecast = [
            Forecast(
                datetime=datetime(2022, 6, 20, 20, 00, 00),
                native_precipitation=1,
                native_temperature=20,
                native_dew_point=2,
            )
        ]


class MockWeatherEntityPrecision(WeatherEntity):
    """Mock a Weather Entity with precision."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_native_temperature = 20.3
        self._attr_native_apparent_temperature = 25.3
        self._attr_native_dew_point = 2.3
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_HALVES


class MockWeatherEntityCompat(WeatherEntity):
    """Mock a Weather Entity using old attributes."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_precipitation_unit = UnitOfLength.MILLIMETERS
        self._attr_pressure = 10
        self._attr_pressure_unit = UnitOfPressure.HPA
        self._attr_temperature = 20
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_visibility = 30
        self._attr_visibility_unit = UnitOfLength.KILOMETERS
        self._attr_wind_speed = 3
        self._attr_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
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


@pytest.mark.parametrize(
    "native_unit", (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS)
)
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfTemperature.CELSIUS, METRIC_SYSTEM),
        (UnitOfTemperature.FAHRENHEIT, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_temperature(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test temperature."""
    hass.config.units = unit_system
    native_value = 38
    apparent_native_value = 45
    dew_point_native_value = 32
    state_value = TemperatureConverter.convert(native_value, native_unit, state_unit)
    apparent_state_value = TemperatureConverter.convert(
        apparent_native_value, native_unit, state_unit
    )

    state_value = TemperatureConverter.convert(native_value, native_unit, state_unit)
    dew_point_state_value = TemperatureConverter.convert(
        dew_point_native_value, native_unit, state_unit
    )
    entity0 = await create_entity(
        hass,
        native_temperature=native_value,
        native_temperature_unit=native_unit,
        native_apparent_temperature=apparent_native_value,
        native_dew_point=dew_point_native_value,
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    apparent_expected = apparent_state_value
    dew_point_expected = dew_point_state_value
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == pytest.approx(
        expected, rel=0.1
    )
    assert float(state.attributes[ATTR_WEATHER_APPARENT_TEMPERATURE]) == pytest.approx(
        apparent_expected, rel=0.1
    )
    assert float(state.attributes[ATTR_WEATHER_DEW_POINT]) == pytest.approx(
        dew_point_expected, rel=0.1
    )
    assert state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == state_unit
    assert float(forecast[ATTR_FORECAST_TEMP]) == pytest.approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_APPARENT_TEMP]) == pytest.approx(
        apparent_expected, rel=0.1
    )
    assert float(forecast[ATTR_FORECAST_DEW_POINT]) == pytest.approx(
        dew_point_expected, rel=0.1
    )
    assert float(forecast[ATTR_FORECAST_TEMP_LOW]) == pytest.approx(expected, rel=0.1)


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfTemperature.CELSIUS, METRIC_SYSTEM),
        (UnitOfTemperature.FAHRENHEIT, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_temperature_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test temperature when the entity does not declare a native unit."""
    hass.config.units = unit_system
    native_value = 38
    dew_point_native_value = 32
    apparent_temp_native_value = 45
    state_value = native_value
    dew_point_state_value = dew_point_native_value
    apparent_temp_state_value = apparent_temp_native_value

    entity0 = await create_entity(
        hass,
        native_temperature=native_value,
        native_temperature_unit=native_unit,
        native_dew_point=dew_point_native_value,
        native_apparent_temperature=apparent_temp_native_value,
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    dew_point_expected = dew_point_state_value
    expected_apparent_temp = apparent_temp_state_value
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == pytest.approx(
        expected, rel=0.1
    )
    assert float(state.attributes[ATTR_WEATHER_DEW_POINT]) == pytest.approx(
        dew_point_expected, rel=0.1
    )
    assert float(state.attributes[ATTR_WEATHER_APPARENT_TEMPERATURE]) == pytest.approx(
        expected_apparent_temp, rel=0.1
    )
    assert state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == state_unit
    assert float(forecast[ATTR_FORECAST_TEMP]) == pytest.approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_DEW_POINT]) == pytest.approx(
        dew_point_expected, rel=0.1
    )
    assert float(forecast[ATTR_FORECAST_TEMP_LOW]) == pytest.approx(expected, rel=0.1)
    assert float(forecast[ATTR_FORECAST_APPARENT_TEMP]) == pytest.approx(
        expected_apparent_temp, rel=0.1
    )


@pytest.mark.parametrize("native_unit", (UnitOfPressure.INHG, UnitOfPressure.INHG))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    ((UnitOfPressure.HPA, METRIC_SYSTEM), (UnitOfPressure.INHG, US_CUSTOMARY_SYSTEM)),
)
async def test_pressure(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test pressure."""
    hass.config.units = unit_system
    native_value = 30
    state_value = PressureConverter.convert(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_pressure=native_value, native_pressure_unit=native_unit
    )
    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == pytest.approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_PRESSURE]) == pytest.approx(expected, rel=1e-2)


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    ((UnitOfPressure.HPA, METRIC_SYSTEM), (UnitOfPressure.INHG, US_CUSTOMARY_SYSTEM)),
)
async def test_pressure_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
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
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == pytest.approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_PRESSURE]) == pytest.approx(expected, rel=1e-2)


@pytest.mark.parametrize(
    "native_unit",
    (
        UnitOfSpeed.MILES_PER_HOUR,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        UnitOfSpeed.METERS_PER_SECOND,
    ),
)
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfSpeed.KILOMETERS_PER_HOUR, METRIC_SYSTEM),
        (UnitOfSpeed.MILES_PER_HOUR, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_wind_speed(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test wind speed."""
    hass.config.units = unit_system
    native_value = 10
    state_value = SpeedConverter.convert(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_wind_speed=native_value, native_wind_speed_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == pytest.approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_WIND_SPEED]) == pytest.approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize(
    "native_unit",
    (
        UnitOfSpeed.MILES_PER_HOUR,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        UnitOfSpeed.METERS_PER_SECOND,
    ),
)
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfSpeed.KILOMETERS_PER_HOUR, METRIC_SYSTEM),
        (UnitOfSpeed.MILES_PER_HOUR, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_wind_gust_speed(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test wind speed."""
    hass.config.units = unit_system
    native_value = 10
    state_value = SpeedConverter.convert(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_wind_gust_speed=native_value, native_wind_speed_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_WIND_GUST_SPEED]) == pytest.approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_WIND_GUST_SPEED]) == pytest.approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfSpeed.KILOMETERS_PER_HOUR, METRIC_SYSTEM),
        (UnitOfSpeed.MILES_PER_HOUR, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_wind_speed_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
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
    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == pytest.approx(
        expected, rel=1e-2
    )
    assert float(forecast[ATTR_FORECAST_WIND_SPEED]) == pytest.approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("native_unit", (UnitOfLength.MILES, UnitOfLength.KILOMETERS))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfLength.KILOMETERS, METRIC_SYSTEM),
        (UnitOfLength.MILES, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_visibility(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test visibility."""
    hass.config.units = unit_system
    native_value = 10
    state_value = DistanceConverter.convert(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_visibility=native_value, native_visibility_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == pytest.approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfLength.KILOMETERS, METRIC_SYSTEM),
        (UnitOfLength.MILES, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_visibility_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test visibility when the entity does not declare a native unit."""
    hass.config.units = unit_system
    native_value = 10
    state_value = native_value

    entity0 = await create_entity(
        hass, native_visibility=native_value, native_visibility_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    expected = state_value
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == pytest.approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("native_unit", (UnitOfLength.INCHES, UnitOfLength.MILLIMETERS))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfLength.MILLIMETERS, METRIC_SYSTEM),
        (UnitOfLength.INCHES, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_precipitation(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
    """Test precipitation."""
    hass.config.units = unit_system
    native_value = 30
    state_value = DistanceConverter.convert(native_value, native_unit, state_unit)

    entity0 = await create_entity(
        hass, native_precipitation=native_value, native_precipitation_unit=native_unit
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    expected = state_value
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == pytest.approx(
        expected, rel=1e-2
    )


@pytest.mark.parametrize("native_unit", (None,))
@pytest.mark.parametrize(
    ("state_unit", "unit_system"),
    (
        (UnitOfLength.MILLIMETERS, METRIC_SYSTEM),
        (UnitOfLength.INCHES, US_CUSTOMARY_SYSTEM),
    ),
)
async def test_precipitation_no_unit(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit: str,
    state_unit: str,
    unit_system,
) -> None:
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
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == pytest.approx(
        expected, rel=1e-2
    )


async def test_wind_bearing_ozone_and_cloud_coverage(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test wind bearing, ozone and cloud coverage."""
    wind_bearing_value = 180
    ozone_value = 10
    cloud_coverage = 75

    entity0 = await create_entity(
        hass,
        wind_bearing=wind_bearing_value,
        ozone=ozone_value,
        cloud_coverage=cloud_coverage,
    )

    state = hass.states.get(entity0.entity_id)
    assert float(state.attributes[ATTR_WEATHER_WIND_BEARING]) == 180
    assert float(state.attributes[ATTR_WEATHER_OZONE]) == 10
    assert float(state.attributes[ATTR_WEATHER_CLOUD_COVERAGE]) == 75


async def test_humidity(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test humidity."""
    humidity_value = 80.2

    entity0 = await create_entity(hass, humidity=humidity_value)

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]
    assert float(state.attributes[ATTR_WEATHER_HUMIDITY]) == 80
    assert float(forecast[ATTR_FORECAST_HUMIDITY]) == 80


async def test_none_forecast(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test that conversion with None values succeeds."""
    entity0 = await create_entity(
        hass,
        native_pressure=None,
        native_pressure_unit=UnitOfPressure.INHG,
        native_wind_speed=None,
        native_wind_speed_unit=UnitOfSpeed.METERS_PER_SECOND,
        native_precipitation=None,
        native_precipitation_unit=UnitOfLength.MILLIMETERS,
    )

    state = hass.states.get(entity0.entity_id)
    forecast = state.attributes[ATTR_FORECAST][0]

    assert forecast.get(ATTR_FORECAST_PRESSURE) is None
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) is None
    assert forecast.get(ATTR_FORECAST_PRECIPITATION) is None


async def test_custom_units(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test custom unit."""
    wind_speed_value = 5
    wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    pressure_value = 110
    pressure_unit = UnitOfPressure.HPA
    temperature_value = 20
    temperature_unit = UnitOfTemperature.CELSIUS
    visibility_value = 11
    visibility_unit = UnitOfLength.KILOMETERS
    precipitation_value = 1.1
    precipitation_unit = UnitOfLength.MILLIMETERS

    set_options = {
        "wind_speed_unit": UnitOfSpeed.MILES_PER_HOUR,
        "precipitation_unit": UnitOfLength.INCHES,
        "pressure_unit": UnitOfPressure.INHG,
        "temperature_unit": UnitOfTemperature.FAHRENHEIT,
        "visibility_unit": UnitOfLength.MILES,
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
        SpeedConverter.convert(
            wind_speed_value, wind_speed_unit, UnitOfSpeed.MILES_PER_HOUR
        ),
        ROUNDING_PRECISION,
    )
    expected_temperature = TemperatureConverter.convert(
        temperature_value, temperature_unit, UnitOfTemperature.FAHRENHEIT
    )
    expected_pressure = round(
        PressureConverter.convert(pressure_value, pressure_unit, UnitOfPressure.INHG),
        ROUNDING_PRECISION,
    )
    expected_visibility = round(
        DistanceConverter.convert(
            visibility_value, visibility_unit, UnitOfLength.MILES
        ),
        ROUNDING_PRECISION,
    )
    expected_precipitation = round(
        DistanceConverter.convert(
            precipitation_value, precipitation_unit, UnitOfLength.INCHES
        ),
        ROUNDING_PRECISION,
    )

    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == pytest.approx(
        expected_wind_speed
    )
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == pytest.approx(
        expected_temperature, rel=0.1
    )
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == pytest.approx(
        expected_pressure
    )
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == pytest.approx(
        expected_visibility
    )
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == pytest.approx(
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
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test backwards compatibility."""
    wind_speed_value = 5
    wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    pressure_value = 110000
    pressure_unit = UnitOfPressure.PA
    temperature_value = 20
    temperature_unit = UnitOfTemperature.CELSIUS
    visibility_value = 11
    visibility_unit = UnitOfLength.KILOMETERS
    precipitation_value = 1
    precipitation_unit = UnitOfLength.MILLIMETERS

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

    assert float(state.attributes[ATTR_WEATHER_WIND_SPEED]) == pytest.approx(
        wind_speed_value * 3.6
    )
    assert (
        state.attributes[ATTR_WEATHER_WIND_SPEED_UNIT]
        == UnitOfSpeed.KILOMETERS_PER_HOUR
    )
    assert float(state.attributes[ATTR_WEATHER_TEMPERATURE]) == pytest.approx(
        temperature_value, rel=0.1
    )
    assert state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == UnitOfTemperature.CELSIUS
    assert float(state.attributes[ATTR_WEATHER_PRESSURE]) == pytest.approx(
        pressure_value / 100
    )
    assert state.attributes[ATTR_WEATHER_PRESSURE_UNIT] == UnitOfPressure.HPA
    assert float(state.attributes[ATTR_WEATHER_VISIBILITY]) == pytest.approx(
        visibility_value
    )
    assert state.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == UnitOfLength.KILOMETERS
    assert float(forecast[ATTR_FORECAST_PRECIPITATION]) == pytest.approx(
        precipitation_value, rel=1e-2
    )
    assert state.attributes[ATTR_WEATHER_PRECIPITATION_UNIT] == UnitOfLength.MILLIMETERS

    assert float(state1.attributes[ATTR_WEATHER_WIND_SPEED]) == pytest.approx(
        wind_speed_value
    )
    assert (
        state1.attributes[ATTR_WEATHER_WIND_SPEED_UNIT]
        == UnitOfSpeed.KILOMETERS_PER_HOUR
    )
    assert float(state1.attributes[ATTR_WEATHER_TEMPERATURE]) == pytest.approx(
        temperature_value, rel=0.1
    )
    assert state1.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == UnitOfTemperature.CELSIUS
    assert float(state1.attributes[ATTR_WEATHER_PRESSURE]) == pytest.approx(
        pressure_value
    )
    assert state1.attributes[ATTR_WEATHER_PRESSURE_UNIT] == UnitOfPressure.HPA
    assert float(state1.attributes[ATTR_WEATHER_VISIBILITY]) == pytest.approx(
        visibility_value
    )
    assert state1.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == UnitOfLength.KILOMETERS
    assert float(forecast1[ATTR_FORECAST_PRECIPITATION]) == pytest.approx(
        precipitation_value, rel=1e-2
    )
    assert (
        state1.attributes[ATTR_WEATHER_PRECIPITATION_UNIT] == UnitOfLength.MILLIMETERS
    )


async def test_backwards_compatibility_convert_values(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test backward compatibility for converting values."""
    wind_speed_value = 5
    wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    pressure_value = 110000
    pressure_unit = UnitOfPressure.PA
    temperature_value = 20
    temperature_unit = UnitOfTemperature.CELSIUS
    visibility_value = 11
    visibility_unit = UnitOfLength.KILOMETERS
    precipitation_value = 1
    precipitation_unit = UnitOfLength.MILLIMETERS

    hass.config.units = US_CUSTOMARY_SYSTEM

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
        SpeedConverter.convert(
            wind_speed_value, wind_speed_unit, UnitOfSpeed.MILES_PER_HOUR
        ),
        ROUNDING_PRECISION,
    )
    expected_temperature = TemperatureConverter.convert(
        temperature_value, temperature_unit, UnitOfTemperature.FAHRENHEIT
    )
    expected_pressure = round(
        PressureConverter.convert(pressure_value, pressure_unit, UnitOfPressure.INHG),
        ROUNDING_PRECISION,
    )
    expected_visibility = round(
        DistanceConverter.convert(
            visibility_value, visibility_unit, UnitOfLength.MILES
        ),
        ROUNDING_PRECISION,
    )
    expected_precipitation = round(
        DistanceConverter.convert(
            precipitation_value, precipitation_unit, UnitOfLength.INCHES
        ),
        ROUNDING_PRECISION,
    )

    assert state.attributes == {
        ATTR_FORECAST: [
            {
                ATTR_FORECAST_PRECIPITATION: pytest.approx(
                    expected_precipitation, rel=0.1
                ),
                ATTR_FORECAST_PRESSURE: pytest.approx(expected_pressure, rel=0.1),
                ATTR_FORECAST_TEMP: pytest.approx(expected_temperature, rel=0.1),
                ATTR_FORECAST_TEMP_LOW: pytest.approx(expected_temperature, rel=0.1),
                ATTR_FORECAST_WIND_BEARING: None,
                ATTR_FORECAST_WIND_SPEED: pytest.approx(expected_wind_speed, rel=0.1),
            }
        ],
        ATTR_FRIENDLY_NAME: "Test",
        ATTR_WEATHER_PRECIPITATION_UNIT: UnitOfLength.INCHES,
        ATTR_WEATHER_PRESSURE: pytest.approx(expected_pressure, rel=0.1),
        ATTR_WEATHER_PRESSURE_UNIT: UnitOfPressure.INHG,
        ATTR_WEATHER_TEMPERATURE: pytest.approx(expected_temperature, rel=0.1),
        ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
        ATTR_WEATHER_VISIBILITY: pytest.approx(expected_visibility, rel=0.1),
        ATTR_WEATHER_VISIBILITY_UNIT: UnitOfLength.MILES,
        ATTR_WEATHER_WIND_SPEED: pytest.approx(expected_wind_speed, rel=0.1),
        ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.MILES_PER_HOUR,
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
    assert weather.native_precipitation_unit == UnitOfLength.MILLIMETERS
    assert weather._precipitation_unit == UnitOfLength.MILLIMETERS
    assert weather.native_pressure == 10
    assert weather.native_pressure_unit == UnitOfPressure.HPA
    assert weather._pressure_unit == UnitOfPressure.HPA
    assert weather.native_temperature == 20
    assert weather.native_temperature_unit == UnitOfTemperature.CELSIUS
    assert weather._temperature_unit == UnitOfTemperature.CELSIUS
    assert weather.native_visibility == 30
    assert weather.native_visibility_unit == UnitOfLength.KILOMETERS
    assert weather._visibility_unit == UnitOfLength.KILOMETERS
    assert weather.native_wind_speed == 3
    assert weather.native_wind_speed_unit == UnitOfSpeed.METERS_PER_SECOND
    assert weather._wind_speed_unit == UnitOfSpeed.KILOMETERS_PER_HOUR


async def test_attr_compatibility(hass: HomeAssistant) -> None:
    """Test the _attr attributes in compatibility mode."""

    weather = MockWeatherEntityCompat()
    weather.hass = hass

    assert weather.condition == ATTR_CONDITION_SUNNY
    assert weather._precipitation_unit == UnitOfLength.MILLIMETERS
    assert weather.pressure == 10
    assert weather._pressure_unit == UnitOfPressure.HPA
    assert weather.temperature == 20
    assert weather._temperature_unit == UnitOfTemperature.CELSIUS
    assert weather.visibility == 30
    assert weather.visibility_unit == UnitOfLength.KILOMETERS
    assert weather.wind_speed == 3
    assert weather._wind_speed_unit == UnitOfSpeed.KILOMETERS_PER_HOUR

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
        ATTR_WEATHER_PRESSURE_UNIT: UnitOfPressure.HPA,
        ATTR_WEATHER_TEMPERATURE: 20.0,
        ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.CELSIUS,
        ATTR_WEATHER_VISIBILITY: 30.0,
        ATTR_WEATHER_VISIBILITY_UNIT: UnitOfLength.KILOMETERS,
        ATTR_WEATHER_WIND_SPEED: 3.0 * 3.6,
        ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
        ATTR_WEATHER_PRECIPITATION_UNIT: UnitOfLength.MILLIMETERS,
    }


async def test_precision_for_temperature(hass: HomeAssistant) -> None:
    """Test the precision for temperature."""

    weather = MockWeatherEntityPrecision()
    weather.hass = hass

    assert weather.condition == ATTR_CONDITION_SUNNY
    assert weather.native_temperature == 20.3
    assert weather.native_dew_point == 2.3
    assert weather._temperature_unit == UnitOfTemperature.CELSIUS
    assert weather.precision == PRECISION_HALVES

    assert weather.state_attributes[ATTR_WEATHER_TEMPERATURE] == 20.5
    assert weather.state_attributes[ATTR_WEATHER_DEW_POINT] == 2.5
