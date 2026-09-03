"""Common fixtures for the Foreca tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyforeca import (
    AirQualityDailyForecast,
    AirQualityForecast,
    CurrentWeather,
    DailyForecast,
    HourlyForecast,
    Location,
)
import pytest

from homeassistant.components.foreca.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry

CURRENT = CurrentWeather(
    time="2026-09-01T17:00+03:00",
    symbol="d200",
    symbol_phrase="partly cloudy",
    temperature=17.4,
    feels_like_temp=16.9,
    rel_humidity=62,
    dew_point=10.1,
    wind_speed=4.2,
    wind_dir=210,
    wind_gust=8.0,
    precip_prob=5,
    cloudiness=40,
    uv_index=2,
    pressure=1013.2,
    visibility=20000,
)

HOURLY = [
    HourlyForecast(
        time="2026-09-01T18:00+03:00",
        symbol="d300",
        temperature=16.0,
        feels_like_temp=15.2,
        wind_speed=3.9,
        wind_gust=7.1,
        wind_dir=200,
        precip_prob=10,
        precip_accum=0.0,
        rel_humidity=70,
        cloudiness=60,
        uv_index=1,
    )
]

DAILY = [
    DailyForecast(
        date="2026-09-02",
        symbol="d310",
        max_temp=18.0,
        min_temp=9.0,
        precip_accum=1.2,
        precip_prob=40,
        max_wind_speed=6.0,
        max_wind_gust=11.0,
        wind_dir=225,
        uv_index=3,
    ),
    DailyForecast(
        date="2026-09-03",
        symbol="d212",
        max_temp=12.0,
        min_temp=4.0,
        precip_accum=0.4,
        max_wind_speed=5.0,
        wind_dir=180,
    ),
]

AIR_QUALITY = AirQualityForecast(
    time="2026-09-01T18:00+03:00",
    pollutant="Ozone",
    pollutant_phrase="Ozone",
    aqi=23,
    aqi_co=2,
    aqi_no2=5,
    aqi_o3=23,
    aqi_so2=1,
    aqi_pm10=8,
    aqi_pm2p5=11,
)

AIR_QUALITY_DAILY = [
    AirQualityDailyForecast(date="2026-09-01", aqi=37, pollutant="Ozone"),
    AirQualityDailyForecast(date="2026-09-02", aqi=34, pollutant="Ozone"),
    AirQualityDailyForecast(date="2026-09-03", aqi=35, pollutant="Ozone"),
    AirQualityDailyForecast(date="2026-09-04", aqi=31, pollutant="Ozone"),
]

LOCATION = Location(
    id=100658225,
    name="Helsinki",
    country="Finland",
    timezone="Europe/Helsinki",
    lon=24.94,
    lat=60.17,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.foreca.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_foreca_client() -> Generator[MagicMock]:
    """Mock the Foreca API client."""
    with (
        patch(
            "homeassistant.components.foreca.coordinator.ForecaApiClient",
            autospec=True,
        ) as client_cls,
        patch(
            "homeassistant.components.foreca.config_flow.ForecaApiClient",
            new=client_cls,
        ),
    ):
        client = client_cls.return_value
        client.location_info = AsyncMock(return_value=LOCATION)
        client.current = AsyncMock(return_value=CURRENT)
        client.forecast_hourly = AsyncMock(return_value=HOURLY)
        client.forecast_daily = AsyncMock(return_value=DAILY)
        client.air_quality_hourly = AsyncMock(return_value=[AIR_QUALITY])
        client.air_quality_daily = AsyncMock(return_value=AIR_QUALITY_DAILY)
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Helsinki",
        entry_id="01JZ4Q1F0RECA0000000000000",
        unique_id="60.1700-24.9400",
        data={
            CONF_API_KEY: "test-key",
            CONF_LATITUDE: 60.17,
            CONF_LONGITUDE: 24.94,
        },
    )
