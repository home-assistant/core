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

    sensor = hass.states.get("sensor.virtual_station_baromabsin")
    assert sensor is not None
    assert sensor.state == "956.112968713878"

    sensor = hass.states.get("sensor.virtual_station_baromrelin")
    assert sensor is not None
    assert sensor.state == "1001.53798593541"

    sensor = hass.states.get("sensor.virtual_station_dailyrainin")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_dewpoint")
    assert sensor is not None
    assert sensor.state == "20.9142888594875"

    sensor = hass.states.get("sensor.virtual_station_feelslike")
    assert sensor is not None
    assert sensor.state == "31.2479199032778"

    sensor = hass.states.get("sensor.virtual_station_hourlyrainin")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_humidity")
    assert sensor is not None
    assert sensor.state == "62.0"

    sensor = hass.states.get("sensor.virtual_station_lastrain")
    assert sensor is not None
    assert sensor.state == "2023-10-30T09:46:40+00:00"

    sensor = hass.states.get("sensor.virtual_station_maxdailygust")
    assert sensor is not None
    assert sensor.state == "37.24022016"

    sensor = hass.states.get("sensor.virtual_station_monthlyrainin")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_solarradiation")
    assert sensor is not None
    assert sensor.state == "36.12"

    sensor = hass.states.get("sensor.virtual_station_tempf")
    assert sensor is not None
    assert sensor.state == "28.9444444444444"

    sensor = hass.states.get("sensor.virtual_station_uv")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_weeklyrainin")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("sensor.virtual_station_winddir")
    assert sensor is not None
    assert sensor.state == "13.0"

    sensor = hass.states.get("sensor.virtual_station_windgustmph")
    assert sensor is not None
    assert sensor.state == "19.52134272"

    sensor = hass.states.get("sensor.virtual_station_windspeedmph")
    assert sensor is not None
    assert sensor.state == "12.56897664"
