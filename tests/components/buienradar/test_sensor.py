"""The tests for the Buienradar sensor platform."""

from datetime import datetime
from http import HTTPStatus
from unittest.mock import MagicMock

from buienradar.constants import (
    CONDITION,
    CONDCODE,
    DETAILED,
    EXACT,
    EXACTNL,
    FORECAST,
    IMAGE,
    PRECIPITATION_FORECAST,
    TIMEFRAME,
    VISIBILITY,
    WINDGUST,
    WINDSPEED,
)
import pytest

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.components.buienradar.sensor import (
    SENSOR_TYPES,
    BrSensor,
)
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_LONGITUDE = 51.5288504
TEST_LATITUDE = 5.4002156

CONDITIONS = ["stationname", "temperature"]
TEST_CFG_DATA = {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE}
TEST_COORDINATES = {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE}


async def test_smoke_test_setup_component(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Smoke test for successfully set-up with default config."""
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.NOT_FOUND
    )
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    for cond in CONDITIONS:
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="buienradar",
            unique_id=f"{TEST_LATITUDE:2.6f}{TEST_LONGITUDE:2.6f}{cond}",
            config_entry=mock_entry,
            original_name=f"Buienradar {cond}",
        )
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    for cond in CONDITIONS:
        state = hass.states.get(f"sensor.buienradar_5_40021651_528850{cond}")
        assert state.state == "unknown"


# Tests for refactored helper methods


def test_load_forecast_data_with_valid_1d_forecast():
    """Test _load_forecast_data with valid 1-day forecast data."""
    description = SensorEntityDescription(key="temperature_1d")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        FORECAST: [
            {"temperature": 15.0},
            {"temperature": 18.0},
        ]
    }
    
    result = sensor._load_forecast_data(data, "temperature_1d")
    
    assert result is True
    assert sensor._attr_native_value == 15.0


def test_load_forecast_data_with_valid_5d_forecast():
    """Test _load_forecast_data with valid 5-day forecast data."""
    description = SensorEntityDescription(key="temperature_5d")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        FORECAST: [
            {"temperature": 15.0},
            {"temperature": 16.0},
            {"temperature": 17.0},
            {"temperature": 18.0},
            {"temperature": 19.0},
        ]
    }
    
    result = sensor._load_forecast_data(data, "temperature_5d")
    
    assert result is True
    assert sensor._attr_native_value == 19.0


def test_load_forecast_data_with_missing_forecast():
    """Test _load_forecast_data when forecast data is missing."""
    description = SensorEntityDescription(key="temperature_3d")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        FORECAST: [
            {"temperature": 15.0},
            {"temperature": 16.0},
        ]
    }
    
    result = sensor._load_forecast_data(data, "temperature_3d")
    
    assert result is False


def test_load_forecast_data_with_windspeed_conversion():
    """Test _load_forecast_data converts wind speed from m/s to km/h."""
    description = SensorEntityDescription(key="windspeed_2d")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        FORECAST: [
            {"windspeed": 10.0},
            {"windspeed": 5.0},
        ]
    }
    
    result = sensor._load_forecast_data(data, "windspeed_2d")
    
    assert result is True
    assert sensor._attr_native_value == 18.0  # 5.0 m/s * 3.6 = 18.0 km/h


def test_load_forecast_data_with_windspeed_none():
    """Test _load_forecast_data when wind speed is None."""
    description = SensorEntityDescription(key="windspeed_1d")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        FORECAST: [
            {"windspeed": None},
        ]
    }
    
    result = sensor._load_forecast_data(data, "windspeed_1d")
    
    assert result is False


def test_update_condition_sensor_with_symbol():
    """Test _update_condition_sensor with symbol sensor type."""
    description = SensorEntityDescription(key="symbol_1d")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    condition_data = {
        EXACTNL: "Zwaar bewolkt",
        IMAGE: "https://example.com/image.png",
    }
    
    result = sensor._update_condition_sensor(condition_data, "symbol_1d")
    
    assert result is True
    assert sensor._attr_native_value == "Zwaar bewolkt"
    assert sensor._attr_entity_picture == "https://example.com/image.png"


def test_update_condition_sensor_with_conditioncode():
    """Test _update_condition_sensor with conditioncode sensor type."""
    description = SensorEntityDescription(key="conditioncode")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    condition_data = {
        CONDCODE: "c",
        IMAGE: "https://example.com/image.png",
    }
    
    result = sensor._update_condition_sensor(condition_data, "conditioncode")
    
    assert result is True
    assert sensor._attr_native_value == "c"
    assert sensor._attr_entity_picture == "https://example.com/image.png"


def test_update_condition_sensor_with_conditiondetailed():
    """Test _update_condition_sensor with conditiondetailed sensor type."""
    description = SensorEntityDescription(key="conditiondetailed")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    condition_data = {
        DETAILED: "partlycloudy",
        IMAGE: "https://example.com/image.png",
    }
    
    result = sensor._update_condition_sensor(condition_data, "conditiondetailed")
    
    assert result is True
    assert sensor._attr_native_value == "partlycloudy"


def test_update_condition_sensor_with_conditionexact():
    """Test _update_condition_sensor with conditionexact sensor type."""
    description = SensorEntityDescription(key="conditionexact")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    condition_data = {
        EXACT: "Partly cloudy",
        IMAGE: "https://example.com/image.png",
    }
    
    result = sensor._update_condition_sensor(condition_data, "conditionexact")
    
    assert result is True
    assert sensor._attr_native_value == "Partly cloudy"


def test_update_condition_sensor_with_condition():
    """Test _update_condition_sensor with condition sensor type."""
    description = SensorEntityDescription(key="condition")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    condition_data = {
        CONDITION: "cloudy",
        IMAGE: "https://example.com/image.png",
    }
    
    result = sensor._update_condition_sensor(condition_data, "condition")
    
    assert result is True
    assert sensor._attr_native_value == "cloudy"


def test_update_condition_sensor_with_no_change():
    """Test _update_condition_sensor when state hasn't changed."""
    description = SensorEntityDescription(key="condition")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    # Set initial state
    sensor._attr_native_value = "cloudy"
    sensor._attr_entity_picture = "https://example.com/image.png"
    
    condition_data = {
        CONDITION: "cloudy",
        IMAGE: "https://example.com/image.png",
    }
    
    result = sensor._update_condition_sensor(condition_data, "condition")
    
    assert result is False


def test_update_condition_sensor_with_none_condition():
    """Test _update_condition_sensor when condition data is None."""
    description = SensorEntityDescription(key="condition")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    result = sensor._update_condition_sensor(None, "condition")
    
    assert result is False


def test_load_precipitation_forecast_data():
    """Test _load_precipitation_forecast_data with valid data."""
    description = SensorEntityDescription(key="precipitation_forecast_average")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        PRECIPITATION_FORECAST: {
            TIMEFRAME: 60,
            "average": 2.5,
            "total": 5.0,
        }
    }
    
    result = sensor._load_precipitation_forecast_data(data, "precipitation_forecast_average")
    
    assert result is True
    assert sensor._attr_native_value == 2.5
    assert sensor._timeframe == 60


def test_load_precipitation_forecast_data_total():
    """Test _load_precipitation_forecast_data for total precipitation."""
    description = SensorEntityDescription(key="precipitation_forecast_total")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        PRECIPITATION_FORECAST: {
            TIMEFRAME: 60,
            "average": 2.5,
            "total": 5.0,
        }
    }
    
    result = sensor._load_precipitation_forecast_data(data, "precipitation_forecast_total")
    
    assert result is True
    assert sensor._attr_native_value == 5.0
    assert sensor._timeframe == 60


def test_load_wind_data_with_valid_windspeed():
    """Test _load_wind_data converts wind speed from m/s to km/h."""
    description = SensorEntityDescription(key="windspeed")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        WINDSPEED: 10.0,
    }
    
    result = sensor._load_wind_data(data, WINDSPEED)
    
    assert result is True
    assert sensor._attr_native_value == 36.0  # 10.0 m/s * 3.6 = 36.0 km/h


def test_load_wind_data_with_valid_windgust():
    """Test _load_wind_data converts wind gust from m/s to km/h."""
    description = SensorEntityDescription(key="windgust")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        WINDGUST: 15.0,
    }
    
    result = sensor._load_wind_data(data, WINDGUST)
    
    assert result is True
    assert sensor._attr_native_value == 54.0  # 15.0 m/s * 3.6 = 54.0 km/h


def test_load_wind_data_with_none_value():
    """Test _load_wind_data when wind speed is None."""
    description = SensorEntityDescription(key="windspeed")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        WINDSPEED: None,
    }
    
    result = sensor._load_wind_data(data, WINDSPEED)
    
    assert result is False


def test_load_visibility_data_with_valid_value():
    """Test _load_visibility_data converts meters to kilometers."""
    description = SensorEntityDescription(key="visibility")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        VISIBILITY: 15000,
    }
    
    result = sensor._load_visibility_data(data, VISIBILITY)
    
    assert result is True
    assert sensor._attr_native_value == 15.0  # 15000 m / 1000 = 15.0 km


def test_load_visibility_data_with_none_value():
    """Test _load_visibility_data when visibility is None."""
    description = SensorEntityDescription(key="visibility")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        VISIBILITY: None,
    }
    
    result = sensor._load_visibility_data(data, VISIBILITY)
    
    assert result is False


def test_load_default_sensor_data_with_temperature():
    """Test _load_default_sensor_data with temperature sensor."""
    description = SensorEntityDescription(key="temperature")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        "temperature": 20.5,
    }
    
    result = sensor._load_default_sensor_data(data, "temperature")
    
    assert result is True
    assert sensor._attr_native_value == 20.5


def test_load_default_sensor_data_with_humidity():
    """Test _load_default_sensor_data with humidity sensor."""
    description = SensorEntityDescription(key="humidity")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        "humidity": 75,
    }
    
    result = sensor._load_default_sensor_data(data, "humidity")
    
    assert result is True
    assert sensor._attr_native_value == 75


def test_load_default_sensor_data_with_pressure():
    """Test _load_default_sensor_data with pressure sensor."""
    description = SensorEntityDescription(key="pressure")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        "pressure": 1013.25,
    }
    
    result = sensor._load_default_sensor_data(data, "pressure")
    
    assert result is True
    assert sensor._attr_native_value == 1013.25


def test_load_default_sensor_data_with_none_value():
    """Test _load_default_sensor_data when sensor value is None."""
    description = SensorEntityDescription(key="temperature")
    sensor = BrSensor("Test", TEST_COORDINATES, description)
    
    data = {
        "temperature": None,
    }
    
    result = sensor._load_default_sensor_data(data, "temperature")
    
    assert result is True
    assert sensor._attr_native_value is None
