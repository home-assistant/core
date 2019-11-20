"""The test for the here_weather weather platform."""
import logging

import herepy
import pytest

from homeassistant.setup import async_setup_component

from . import (
    APP_CODE,
    APP_ID,
    LATITUDE,
    LOCATION_NAME,
    LONGITUDE,
    PLATFORM,
    ZIP_CODE,
    build_coordinates_mock_url,
    build_location_name_mock_url,
    build_zip_code_imperial_mock_url,
    build_zip_code_mock_url,
)

from tests.common import load_fixture

DOMAIN = "weather"


@pytest.fixture
def requests_mock_credentials_check(requests_mock):
    """Add the url used in the api validation to all requests mock."""
    product = herepy.WeatherProductType.forecast_astronomy
    response_url = build_zip_code_mock_url(APP_ID, APP_CODE, ZIP_CODE, product)
    requests_mock.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_forecasts_astronomy.json"),
    )
    return requests_mock


@pytest.fixture
def requests_mock_invalid_credentials(requests_mock):
    """Add the url for invalid credentials to requests mock."""
    product = herepy.WeatherProductType.forecast_astronomy
    response_url = build_zip_code_mock_url(APP_ID, APP_CODE, ZIP_CODE, product)
    requests_mock.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_error_unauthorized.json"),
    )
    return requests_mock


@pytest.fixture
def requests_mock_location_name(requests_mock_credentials_check):
    """Add the url used in a request with location_name to requests mock."""
    product = herepy.WeatherProductType.forecast_astronomy
    response_url = build_location_name_mock_url(
        APP_ID, APP_CODE, LOCATION_NAME, product
    )
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_forecasts_astronomy.json"),
    )
    return requests_mock_credentials_check


@pytest.fixture
def requests_mock_coordinates(requests_mock_credentials_check):
    """Add the url used in a request with coordinates to requests mock."""
    product = herepy.WeatherProductType.forecast_astronomy
    response_url = build_coordinates_mock_url(
        APP_ID, APP_CODE, LATITUDE, LONGITUDE, product
    )
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_forecasts_astronomy.json"),
    )
    return requests_mock_credentials_check


@pytest.fixture
def requests_mock_zip_code_imperial(requests_mock_credentials_check):
    """Add the url used in a request with zip_code to requests mock."""
    product = herepy.WeatherProductType.observation
    response_url = build_zip_code_imperial_mock_url(APP_ID, APP_CODE, ZIP_CODE, product)
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_observation_imperial.json"),
    )
    return requests_mock_credentials_check


@pytest.fixture
def requests_mock_forecast_7days(requests_mock_credentials_check):
    """Add the url used in a request with forecast_7days to requests mock."""
    product = herepy.WeatherProductType.forecast_7days
    response_url = build_location_name_mock_url(
        APP_ID, APP_CODE, LOCATION_NAME, product
    )
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_forecasts.json"),
    )
    return requests_mock_credentials_check


@pytest.fixture
def requests_mock_forecast_hourly(requests_mock_credentials_check):
    """Add the url used in a request with forecast_hourly to requests mock."""
    product = herepy.WeatherProductType.forecast_hourly
    response_url = build_location_name_mock_url(
        APP_ID, APP_CODE, LOCATION_NAME, product
    )
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_forecasts_hourly.json"),
    )
    return requests_mock_credentials_check


@pytest.fixture
def requests_mock_forecast_7days_simple(requests_mock_credentials_check):
    """Add the url used in a request with forecast_7days_simple to requests mock."""
    product = herepy.WeatherProductType.forecast_7days_simple
    response_url = build_location_name_mock_url(
        APP_ID, APP_CODE, LOCATION_NAME, product
    )
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_weather/destination_weather_forecasts_simple.json"),
    )
    return requests_mock_credentials_check


@pytest.fixture
def requests_mock_invalid_request(requests_mock_credentials_check):
    """Add the url used in an invalid request to requests mock."""
    product = herepy.WeatherProductType.observation
    response_url = build_zip_code_mock_url(APP_ID, APP_CODE, ZIP_CODE, product)
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture(
            "here_weather/destination_weather_error_invalid_request.json"
        ),
    )
    return requests_mock_credentials_check


async def test_invalid_credentials(hass, requests_mock_invalid_credentials, caplog):
    """Test that invalid credentials error is correctly handled."""
    caplog.set_level(logging.ERROR)
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "zip_code": ZIP_CODE,
            "mode": "forecast_7days",
            "app_id": APP_ID,
            "app_code": APP_CODE,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    assert len(caplog.records) == 1
    assert "Invalid credentials" in caplog.text


async def test_location_name(hass, requests_mock_location_name):
    """Test that location_name option works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "location_name": LOCATION_NAME,
            "mode": "forecast_7days",
            "app_id": APP_ID,
            "app_code": APP_CODE,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    sensor_name = sensor_name = f"{DOMAIN}.test"
    sensor = hass.states.get(sensor_name)
    assert sensor.state == "cloudy"


async def test_coordinates(hass, requests_mock_coordinates):
    """Test that lat/lon option works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "mode": "forecast_7days",
            "app_id": APP_ID,
            "app_code": APP_CODE,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    sensor_name = sensor_name = f"{DOMAIN}.test"
    sensor = hass.states.get(sensor_name)
    assert sensor.state == "cloudy"


async def test_imperial(hass, requests_mock_zip_code_imperial):
    """Test that imperial mode works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "zip_code": ZIP_CODE,
            "mode": "observation",
            "app_id": APP_ID,
            "app_code": APP_CODE,
            "unit_system": "imperial",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    sensor_name = f"{DOMAIN}.test"
    sensor = hass.states.get(sensor_name)
    assert (
        sensor.attributes.get("temperature") == 8
    )  # Gets converted because standard hass config is metric


async def test_forecast_7days(hass, requests_mock_forecast_7days):
    """Test that forecast_7days option works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "location_name": LOCATION_NAME,
            "mode": "forecast_7days",
            "app_id": APP_ID,
            "app_code": APP_CODE,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    sensor_name = sensor_name = f"{DOMAIN}.test"
    sensor = hass.states.get(sensor_name)
    assert sensor.state == "cloudy"


async def test_forecast_7days_simple(hass, requests_mock_forecast_7days_simple):
    """Test that forecast_7days_simple option works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "location_name": LOCATION_NAME,
            "mode": "forecast_7days_simple",
            "app_id": APP_ID,
            "app_code": APP_CODE,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    sensor_name = sensor_name = f"{DOMAIN}.test"
    sensor = hass.states.get(sensor_name)
    assert sensor.state == "cloudy"


async def test_forecast_forecast_hourly(hass, requests_mock_forecast_hourly):
    """Test that forecast_hourly option works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "location_name": LOCATION_NAME,
            "mode": "forecast_hourly",
            "app_id": APP_ID,
            "app_code": APP_CODE,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    sensor_name = sensor_name = f"{DOMAIN}.test"
    sensor = hass.states.get(sensor_name)
    assert sensor.state == "cloudy"


async def test_invalid_request(hass, requests_mock_invalid_request, caplog):
    """Test that invalid credentials error is correctly handled."""
    caplog.set_level(logging.ERROR)
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "zip_code": ZIP_CODE,
            "mode": "observation",
            "app_id": APP_ID,
            "app_code": APP_CODE,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    assert len(caplog.records) == 1
    assert "Error during sensor update" in caplog.text

    sensor_name = sensor_name = f"{DOMAIN}.test"
    sensor = hass.states.get(sensor_name)
    assert sensor.state == "unknown"
