"""Test Ambient Weather Network sensors."""

from aioambient import OpenAPI
from freezegun import freeze_time

from homeassistant.core import HomeAssistant

from .conftest import setup_platform


@freeze_time("2023-11-07")
async def test_sensors(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test all sensors."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.virtual_station_absolute_pressure")
    assert sensor is not None
    assert sensor.state == "956.112968713878"

    sensor = hass.states.get("sensor.virtual_station_relative_pressure")
    assert sensor is not None
    assert sensor.state == "1001.53798593541"

    sensor = hass.states.get("sensor.virtual_station_daily_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_dew_point")
    assert sensor is not None
    assert sensor.state == "26.8333333333333"

    sensor = hass.states.get("sensor.virtual_station_feels_like")
    assert sensor is not None
    assert sensor.state == "30.3888888888889"

    sensor = hass.states.get("sensor.virtual_station_hourly_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_humidity")
    assert sensor is not None
    assert sensor.state == "62.0"

    sensor = hass.states.get("sensor.virtual_station_last_rain")
    assert sensor is not None
    assert sensor.state == "2023-10-30T09:46:40+00:00"

    sensor = hass.states.get("sensor.virtual_station_max_daily_gust")
    assert sensor is not None
    assert sensor.state == "37.24022016"

    sensor = hass.states.get("sensor.virtual_station_monthly_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_solar_radiation")
    assert sensor is not None
    assert sensor.state == "36.12"

    sensor = hass.states.get("sensor.virtual_station_temperature")
    assert sensor is not None
    assert sensor.state == "28.9444444444444"

    sensor = hass.states.get("sensor.virtual_station_uv_index")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_weekly_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_wind_direction")
    assert sensor is not None
    assert sensor.state == "13.0"

    sensor = hass.states.get("sensor.virtual_station_wind_gust")
    assert sensor is not None
    assert sensor.state == "19.52134272"

    sensor = hass.states.get("sensor.virtual_station_wind_speed")
    assert sensor is not None
    assert sensor.state == "12.56897664"
