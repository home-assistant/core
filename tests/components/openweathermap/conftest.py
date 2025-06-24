"""Configure tests for the OpenWeatherMap integration."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from pyopenweathermap import (
    AirPollutionReport,
    CurrentAirPollution,
    CurrentWeather,
    DailyTemperature,
    DailyWeatherForecast,
    MinutelyWeatherForecast,
    WeatherCondition,
    WeatherReport,
)
from pyopenweathermap.client.owm_abstract_client import OWMClient
import pytest

from homeassistant.components.openweathermap.const import DEFAULT_LANGUAGE, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)

from tests.common import MockConfigEntry, patch

API_KEY = "test_api_key"
LATITUDE = 12.34
LONGITUDE = 56.78
NAME = "openweathermap"


@pytest.fixture
def mode(request: pytest.FixtureRequest) -> str:
    """Return mode passed in parameter."""
    return request.param


@pytest.fixture
def mock_config_entry(mode: str) -> MockConfigEntry:
    """Fixture for creating a mock OpenWeatherMap config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: API_KEY,
            CONF_LATITUDE: LATITUDE,
            CONF_LONGITUDE: LONGITUDE,
            CONF_NAME: NAME,
        },
        options={
            CONF_MODE: mode,
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
        },
        entry_id="test",
        version=5,
        unique_id=f"{LATITUDE}-{LONGITUDE}",
    )


@pytest.fixture
def owm_client_mock() -> Generator[AsyncMock]:
    """Mock OWMClient."""
    client = AsyncMock(spec=OWMClient, autospec=True)
    current_weather = CurrentWeather(
        date_time=datetime.fromtimestamp(1714063536, tz=UTC),
        temperature=6.84,
        feels_like=2.07,
        pressure=1000,
        humidity=82,
        dew_point=3.99,
        uv_index=0.13,
        cloud_coverage=75,
        visibility=10000,
        wind_speed=9.83,
        wind_bearing=199,
        wind_gust=None,
        rain={"1h": 1.21},
        snow=None,
        condition=WeatherCondition(
            id=803,
            main="Clouds",
            description="broken clouds",
            icon="04d",
        ),
    )
    daily_weather_forecast = DailyWeatherForecast(
        date_time=datetime.fromtimestamp(1714063536, tz=UTC),
        summary="There will be clear sky until morning, then partly cloudy",
        temperature=DailyTemperature(
            day=18.76,
            min=8.11,
            max=21.26,
            night=13.06,
            evening=20.51,
            morning=8.47,
        ),
        feels_like=DailyTemperature(
            day=18.76,
            min=8.11,
            max=21.26,
            night=13.06,
            evening=20.51,
            morning=8.47,
        ),
        pressure=1015,
        humidity=62,
        dew_point=11.34,
        wind_speed=8.14,
        wind_bearing=168,
        wind_gust=11.81,
        condition=WeatherCondition(
            id=803,
            main="Clouds",
            description="broken clouds",
            icon="04d",
        ),
        cloud_coverage=84,
        precipitation_probability=0,
        uv_index=4.06,
        rain=0,
        snow=0,
    )
    minutely_weather_forecast = [
        MinutelyWeatherForecast(date_time=1728672360, precipitation=0),
        MinutelyWeatherForecast(date_time=1728672420, precipitation=1.23),
        MinutelyWeatherForecast(date_time=1728672480, precipitation=4.5),
        MinutelyWeatherForecast(date_time=1728672540, precipitation=0),
    ]
    client.get_weather.return_value = WeatherReport(
        current_weather, minutely_weather_forecast, [], [daily_weather_forecast]
    )
    current_air_pollution = CurrentAirPollution(
        date_time=datetime.fromtimestamp(1714063537, tz=UTC),
        aqi=3,
        co=125.55,
        no=0.11,
        no2=0.78,
        o3=101.98,
        so2=0.59,
        pm2_5=4.48,
        pm10=4.77,
        nh3=4.62,
    )
    client.get_air_pollution.return_value = AirPollutionReport(
        current_air_pollution, []
    )
    client.validate_key.return_value = True
    with (
        patch(
            "homeassistant.components.openweathermap.create_owm_client",
            return_value=client,
        ),
        patch(
            "homeassistant.components.openweathermap.utils.create_owm_client",
            return_value=client,
        ),
    ):
        yield client
