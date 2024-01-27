"""Test Ambient Weather Network sensors."""

from aioambient import OpenAPI
from freezegun import freeze_time
import pytest

from homeassistant.core import HomeAssistant

from .conftest import setup_platform


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test all sensors."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_a_absolute_pressure")
    assert sensor is not None
    assert sensor.state == "977.616536580043"

    sensor = hass.states.get("sensor.station_a_relative_pressure")
    assert sensor is not None
    assert sensor.state == "1001.89694313129"

    sensor = hass.states.get("sensor.station_a_daily_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.station_a_dew_point")
    assert sensor is not None
    assert sensor.state == "27.7777777777778"

    sensor = hass.states.get("sensor.station_a_feels_like")
    assert sensor is not None
    assert sensor.state == "29.4444444444444"

    sensor = hass.states.get("sensor.station_a_hourly_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.station_a_humidity")
    assert sensor is not None
    assert sensor.state == "60"

    sensor = hass.states.get("sensor.station_a_last_rain")
    assert sensor is not None
    assert sensor.state == "2023-10-30T09:45:00+00:00"

    sensor = hass.states.get("sensor.station_a_max_daily_gust")
    assert sensor is not None
    assert sensor.state == "36.72523008"

    sensor = hass.states.get("sensor.station_a_monthly_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.station_a_irradiance")
    assert sensor is not None
    assert sensor.state == "37.64"

    sensor = hass.states.get("sensor.station_a_temperature")
    assert sensor is not None
    assert sensor.state == "28.2777777777778"

    sensor = hass.states.get("sensor.station_a_uv_index")
    assert sensor is not None
    assert sensor.state == "0"

    sensor = hass.states.get("sensor.station_a_weekly_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.station_a_wind_direction")
    assert sensor is not None
    assert sensor.state == "11"

    sensor = hass.states.get("sensor.station_a_wind_gust")
    assert sensor is not None
    assert sensor.state == "14.75768448"

    sensor = hass.states.get("sensor.station_a_wind_speed")
    assert sensor is not None
    assert sensor.state == "14.03347968"


@freeze_time("2023-11-09")
@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors_with_outdated_data(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test that the sensor is not populated if the last data is outdated."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_a_absolute_pressure")
    assert sensor is None


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["BB:BB:BB:BB:BB:BB"], indirect=True)
async def test_sensors_with_no_data(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test that the sensor is not populated if the last data is absent."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_b_absolute_pressure")
    assert sensor is None


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["CC:CC:CC:CC:CC:CC"], indirect=True)
async def test_sensors_with_no_update_time(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test that the sensor is not populated if the update time is missing."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_c_absolute_pressure")
    assert sensor is None
