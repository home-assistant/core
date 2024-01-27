"""Test Ambient Weather Network sensors."""

from unittest.mock import patch

from aioambient import OpenAPI
from aioambient.errors import RequestError
from freezegun import freeze_time
import pytest

from homeassistant.components import ambient_network
from homeassistant.core import HomeAssistant

from .conftest import setup_platform


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test all sensors under normal operation."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_a_absolute_pressure")
    assert sensor is not None
    assert float(sensor.state) == pytest.approx(977.61653)

    sensor = hass.states.get("sensor.station_a_relative_pressure")
    assert sensor is not None
    assert float(sensor.state) == pytest.approx(1001.89694)

    sensor = hass.states.get("sensor.station_a_daily_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.station_a_dew_point")
    assert sensor is not None
    assert float(sensor.state) == pytest.approx(27.77777)

    sensor = hass.states.get("sensor.station_a_feels_like")
    assert sensor is not None
    assert float(sensor.state) == pytest.approx(29.44444)

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
    assert float(sensor.state) == pytest.approx(36.7252)

    sensor = hass.states.get("sensor.station_a_monthly_rain")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.station_a_irradiance")
    assert sensor is not None
    assert sensor.state == "37.64"

    sensor = hass.states.get("sensor.station_a_temperature")
    assert sensor is not None
    assert float(sensor.state) == pytest.approx(28.27777)

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
    assert float(sensor.state) == pytest.approx(14.75768)

    sensor = hass.states.get("sensor.station_a_wind_speed")
    assert sensor is not None
    assert float(sensor.state) == pytest.approx(14.03347)


@freeze_time("2023-11-09")
@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors_with_stale_data(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test that the sensors are not populated if the data is stale."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_a_absolute_pressure")
    assert sensor is None


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["BB:BB:BB:BB:BB:BB"], indirect=True)
async def test_sensors_with_no_data(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test that the sensors are not populated if the last data is absent."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_b_absolute_pressure")
    assert sensor is None


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["CC:CC:CC:CC:CC:CC"], indirect=True)
async def test_sensors_with_no_update_time(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient
) -> None:
    """Test that the sensors are not populated if the update time is missing."""
    await setup_platform(hass, open_api, config_entry)

    sensor = hass.states.get("sensor.station_c_absolute_pressure")
    assert sensor is None


@freeze_time("2023-11-08")
@pytest.mark.parametrize("config_entry", ["AA:AA:AA:AA:AA:AA"], indirect=True)
async def test_sensors_disappearing(
    hass: HomeAssistant, open_api: OpenAPI, config_entry, aioambient, caplog
) -> None:
    """Test that we log errors properly."""

    # Normal state, sensor is available.
    await setup_platform(hass, open_api, config_entry)
    coordinator = hass.data[ambient_network.DOMAIN][config_entry.entry_id]
    sensor = hass.states.get("sensor.station_a_absolute_pressure")
    assert sensor is not None
    assert float(sensor.state) == pytest.approx(977.61653)

    # Sensor becomes unavailable if the network is unavailable. Log message
    # should only show up once.
    for _ in range(5):
        with patch.object(open_api, "get_device_details", side_effect=RequestError()):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        sensor = hass.states.get("sensor.station_a_absolute_pressure")
        assert sensor is not None
        assert sensor.state == "unknown"
        assert caplog.text.count("Cannot connect to Ambient Network") == 1

    # Network comes back. Sensor should start reporting again. Log message
    # should only show up once.
    for _ in range(5):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        sensor = hass.states.get("sensor.station_a_absolute_pressure")
        assert sensor is not None
        assert float(sensor.state) == pytest.approx(977.61653)
        assert caplog.text.count("Station 'Station A' is back online") == 1
