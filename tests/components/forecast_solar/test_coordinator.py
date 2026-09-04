"""Test the Forecast.Solar coordinator."""

import pytest

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_MODULES_POWER,
    DOMAIN,
    SUBENTRY_TYPE_PLANE,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def sensor_plane_config_entry() -> MockConfigEntry:
    """Return a config entry whose main plane reads azimuth from a sensor."""
    return MockConfigEntry(
        title="Sensor House",
        unique_id="unique-sensor",
        version=3,
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42},
        options={},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="mock_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / sensor.roof_azimuth / 5100W",
                unique_id=None,
            ),
        ],
    )


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_rereads_azimuth_sensor_on_each_update(
    hass: HomeAssistant,
    sensor_plane_config_entry: MockConfigEntry,
) -> None:
    """Test the azimuth sensor is read at setup and a changed value on refresh.

    UI stores 0-360 (0=North), library expects -180..180 (0=South).
    """
    hass.states.async_set("sensor.roof_azimuth", "100", {"unit_of_measurement": "°"})
    sensor_plane_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(sensor_plane_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = sensor_plane_config_entry.runtime_data
    assert coordinator.forecast.azimuth == 100 - 180

    hass.states.async_set("sensor.roof_azimuth", "200", {"unit_of_measurement": "°"})
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.forecast.azimuth == 200 - 180


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_update_fails_when_sensor_unavailable(
    hass: HomeAssistant,
    sensor_plane_config_entry: MockConfigEntry,
) -> None:
    """Test an unavailable sensor fails that poll instead of setup."""
    hass.states.async_set("sensor.roof_azimuth", "100", {"unit_of_measurement": "°"})
    sensor_plane_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(sensor_plane_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = sensor_plane_config_entry.runtime_data
    hass.states.async_set("sensor.roof_azimuth", "unavailable")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_update_fails_when_sensor_out_of_range(
    hass: HomeAssistant,
    sensor_plane_config_entry: MockConfigEntry,
) -> None:
    """Test an out-of-range sensor value fails setup."""
    hass.states.async_set("sensor.roof_azimuth", "500", {"unit_of_measurement": "°"})
    sensor_plane_config_entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(sensor_plane_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False


@pytest.fixture
def declination_sensor_plane_config_entry() -> MockConfigEntry:
    """Return a config entry whose main plane reads declination from a sensor."""
    return MockConfigEntry(
        title="Sensor House",
        unique_id="unique-declination-sensor",
        version=3,
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42},
        options={},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION_SENSOR: "sensor.roof_declination",
                    CONF_AZIMUTH: 190,
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="mock_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="sensor.roof_declination / 190° / 5100W",
                unique_id=None,
            ),
        ],
    )


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_resolves_declination_sensor_on_setup(
    hass: HomeAssistant,
    declination_sensor_plane_config_entry: MockConfigEntry,
) -> None:
    """Test the coordinator reads the declination sensor's value at setup."""
    hass.states.async_set("sensor.roof_declination", "42", {"unit_of_measurement": "°"})
    declination_sensor_plane_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(
        declination_sensor_plane_config_entry.entry_id
    )
    await hass.async_block_till_done()

    coordinator = declination_sensor_plane_config_entry.runtime_data
    assert coordinator.forecast.declination == 42


@pytest.fixture
def sensor_extra_plane_config_entry() -> MockConfigEntry:
    """Return a config entry with a sensor-backed extra (non-main) plane."""
    return MockConfigEntry(
        title="Sensor House",
        unique_id="unique-extra-sensor",
        version=3,
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42},
        options={"api_key": "abcdef1234567890"},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH: 190,
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="main_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / 190° / 5100W",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_DECLINATION_SENSOR: "sensor.extra_declination",
                    CONF_AZIMUTH_SENSOR: "sensor.extra_azimuth",
                    CONF_MODULES_POWER: 3000,
                },
                subentry_id="extra_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="sensor.extra_declination / sensor.extra_azimuth / 3000W",
                unique_id=None,
            ),
        ],
    )


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_resolves_extra_plane_sensors_on_setup(
    hass: HomeAssistant,
    sensor_extra_plane_config_entry: MockConfigEntry,
) -> None:
    """Test a sensor-backed extra plane's angles resolve from its sensors."""
    hass.states.async_set(
        "sensor.extra_declination", "20", {"unit_of_measurement": "°"}
    )
    hass.states.async_set("sensor.extra_azimuth", "160", {"unit_of_measurement": "°"})
    sensor_extra_plane_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(sensor_extra_plane_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = sensor_extra_plane_config_entry.runtime_data
    extra_plane = coordinator.forecast.planes[0]
    assert extra_plane.declination == 20
    assert extra_plane.azimuth == 160 - 180


@pytest.fixture
def tracked_location_config_entry() -> MockConfigEntry:
    """Return a config entry with no fixed location, tracking HA's home location."""
    return MockConfigEntry(
        title="Tracked Location House",
        unique_id="unique-tracked-location",
        version=3,
        domain=DOMAIN,
        data={},
        options={},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH: 190,
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="mock_plane_id",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / 190° / 5100W",
                unique_id=None,
            ),
        ],
    )


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_retracks_home_location_on_update(
    hass: HomeAssistant,
    tracked_location_config_entry: MockConfigEntry,
) -> None:
    """Test HA's home location is used at setup and a changed value on refresh."""
    hass.config.latitude = 51.5
    hass.config.longitude = -0.1
    tracked_location_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(tracked_location_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = tracked_location_config_entry.runtime_data
    assert coordinator.forecast.latitude == 51.5

    hass.config.latitude = 48.85
    hass.config.longitude = 2.35
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.forecast.latitude == 48.85
    assert coordinator.forecast.longitude == 2.35
