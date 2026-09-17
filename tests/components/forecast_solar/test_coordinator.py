"""Test the Forecast.Solar coordinator."""

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock, patch

from forecast_solar import ForecastSolarConnectionError
from freezegun.api import FrozenDateTimeFactory
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
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN

from tests.common import MockConfigEntry, async_fire_time_changed

AZIMUTH_SENSOR = "sensor.roof_azimuth"
DECLINATION_SENSOR = "sensor.roof_declination"
DEGREES = {"unit_of_measurement": "°"}

FIXED_LOCATION = {CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42}


def _config_entry(
    *planes: dict[str, Any],
    entry_data: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Return a config entry with a plane subentry per given plane data."""
    return MockConfigEntry(
        title="Sensor House",
        unique_id="unique-sensor",
        version=3,
        domain=DOMAIN,
        data=entry_data,
        options=options or {},
        subentries_data=[
            ConfigSubentryData(
                data=plane,
                subentry_id=f"plane_{index}",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title=f"Plane {index}",
                unique_id=None,
            )
            for index, plane in enumerate(planes)
        ],
    )


AZIMUTH_SENSOR_PLANE = {
    CONF_DECLINATION: 30,
    CONF_AZIMUTH_SENSOR: AZIMUTH_SENSOR,
    CONF_MODULES_POWER: 5100,
}


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_rereads_azimuth_sensor_on_each_update(
    hass: HomeAssistant,
) -> None:
    """Test the azimuth sensor is read at setup and a changed value on refresh.

    UI stores 0-360 (0=North), library expects -180..180 (0=South).
    """
    hass.states.async_set(AZIMUTH_SENSOR, "100", DEGREES)
    entry = _config_entry(AZIMUTH_SENSOR_PLANE, entry_data=FIXED_LOCATION)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.forecast.azimuth == 100 - 180

    hass.states.async_set(AZIMUTH_SENSOR, "200", DEGREES)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.forecast.azimuth == 200 - 180


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_normalises_compass_azimuth(hass: HomeAssistant) -> None:
    """Test a compass sensor reporting -180..180 is normalised, not rejected."""
    hass.states.async_set(AZIMUTH_SENSOR, "-90", DEGREES)
    entry = _config_entry(AZIMUTH_SENSOR_PLANE, entry_data=FIXED_LOCATION)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.forecast.azimuth == 270 - 180


@pytest.mark.parametrize(
    ("states", "translation_key"),
    [
        pytest.param({}, "sensor_no_state", id="no_state"),
        pytest.param(
            {AZIMUTH_SENSOR: "unavailable"}, "sensor_invalid", id="unavailable"
        ),
        pytest.param({AZIMUTH_SENSOR: "unknown"}, "sensor_invalid", id="unknown"),
        pytest.param({AZIMUTH_SENSOR: "north"}, "sensor_invalid", id="not_a_number"),
        pytest.param({AZIMUTH_SENSOR: "500"}, "sensor_invalid", id="above_range"),
        pytest.param({AZIMUTH_SENSOR: "-200"}, "sensor_invalid", id="below_range"),
    ],
)
@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_setup_retries_on_unusable_sensor(
    hass: HomeAssistant,
    states: dict[str, str],
    translation_key: str,
) -> None:
    """Test an unusable sensor retries setup with a translated reason."""
    for entity_id, state in states.items():
        hass.states.async_set(entity_id, state, DEGREES)
    entry = _config_entry(AZIMUTH_SENSOR_PLANE, entry_data=FIXED_LOCATION)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == translation_key


async def test_coordinator_update_fails_until_sensor_recovers(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing sensor fails updates, and its recovery refreshes right away."""
    hass.states.async_set(AZIMUTH_SENSOR, "100", DEGREES)
    entry = _config_entry(AZIMUTH_SENSOR_PLANE, entry_data=FIXED_LOCATION)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    estimate_calls = mock_forecast_solar.estimate.call_count

    # While updates succeed, a sensor change waits for the schedule.
    hass.states.async_set(AZIMUTH_SENSOR, "unavailable", DEGREES)
    await hass.async_block_till_done()
    assert mock_forecast_solar.estimate.call_count == estimate_calls

    await coordinator.async_refresh()
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator.last_exception.translation_key == "sensor_invalid"
    # A persistent failure is logged once, not on every poll.
    assert caplog.text.count("Error fetching forecast_solar data") == 1
    assert not [
        record
        for record in caplog.records
        if record.name.startswith("homeassistant.components.forecast_solar")
        and record.levelno == logging.WARNING
    ]
    # The sensor was rejected before calling the API.
    assert mock_forecast_solar.estimate.call_count == estimate_calls

    hass.states.async_set(AZIMUTH_SENSOR, "200", DEGREES)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert coordinator.forecast.azimuth == 200 - 180
    assert mock_forecast_solar.estimate.call_count == estimate_calls + 1


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_planes_sharing_sensor_request_one_refresh(
    hass: HomeAssistant,
) -> None:
    """Test a sensor shared by planes requests a single refresh when it recovers."""
    hass.states.async_set(AZIMUTH_SENSOR, "100", DEGREES)
    entry = _config_entry(
        AZIMUTH_SENSOR_PLANE,
        AZIMUTH_SENSOR_PLANE,
        entry_data=FIXED_LOCATION,
        options={CONF_API_KEY: "abcdef1234567890"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    hass.states.async_set(AZIMUTH_SENSOR, "unavailable", DEGREES)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # Mocked so the update stays failed, as it would while a real API call is pending.
    with patch.object(coordinator, "async_request_refresh") as request_refresh:
        hass.states.async_set(AZIMUTH_SENSOR, "200", DEGREES)
        await hass.async_block_till_done()

    request_refresh.assert_called_once()


async def test_coordinator_recovery_refreshes_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test sensor changes during a recovery refresh don't queue another API call."""
    hass.states.async_set(AZIMUTH_SENSOR, "100", DEGREES)
    entry = _config_entry(AZIMUTH_SENSOR_PLANE, entry_data=FIXED_LOCATION)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    hass.states.async_set(AZIMUTH_SENSOR, "unavailable", DEGREES)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    estimate_calls = mock_forecast_solar.estimate.call_count

    api_call_done = asyncio.Event()

    async def _estimate() -> MagicMock:
        await api_call_done.wait()
        return mock_forecast_solar.estimate.return_value

    mock_forecast_solar.estimate.side_effect = _estimate

    # A compass keeps changing while the refresh its recovery started is in flight.
    hass.states.async_set(AZIMUTH_SENSOR, "200", DEGREES)
    await asyncio.sleep(0)
    hass.states.async_set(AZIMUTH_SENSOR, "210", DEGREES)
    api_call_done.set()
    await hass.async_block_till_done()

    freezer.tick(REQUEST_REFRESH_DEFAULT_COOLDOWN + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert mock_forecast_solar.estimate.call_count == estimate_calls + 1


async def test_coordinator_api_failure_waits_for_schedule(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test sensor changes don't retry an update that failed at the API."""
    hass.states.async_set(AZIMUTH_SENSOR, "100", DEGREES)
    entry = _config_entry(AZIMUTH_SENSOR_PLANE, entry_data=FIXED_LOCATION)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    mock_forecast_solar.estimate.side_effect = ForecastSolarConnectionError
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    estimate_calls = mock_forecast_solar.estimate.call_count

    # A compass on a moving vehicle changes constantly; that must not spend the rate limit.
    hass.states.async_set(AZIMUTH_SENSOR, "110", DEGREES)
    await hass.async_block_till_done()

    assert mock_forecast_solar.estimate.call_count == estimate_calls


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_resolves_declination_sensor_on_setup(
    hass: HomeAssistant,
) -> None:
    """Test the coordinator reads the declination sensor's value at setup."""
    hass.states.async_set(DECLINATION_SENSOR, "42", DEGREES)
    entry = _config_entry(
        {
            CONF_DECLINATION_SENSOR: DECLINATION_SENSOR,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
        },
        entry_data=FIXED_LOCATION,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.forecast.declination == 42


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_resolves_extra_plane_sensors_on_setup(
    hass: HomeAssistant,
) -> None:
    """Test a sensor-backed extra plane's angles resolve from its sensors."""
    hass.states.async_set("sensor.extra_declination", "20", DEGREES)
    hass.states.async_set("sensor.extra_azimuth", "160", DEGREES)
    entry = _config_entry(
        {CONF_DECLINATION: 30, CONF_AZIMUTH: 190, CONF_MODULES_POWER: 5100},
        {
            CONF_DECLINATION_SENSOR: "sensor.extra_declination",
            CONF_AZIMUTH_SENSOR: "sensor.extra_azimuth",
            CONF_MODULES_POWER: 3000,
        },
        entry_data=FIXED_LOCATION,
        options={CONF_API_KEY: "abcdef1234567890"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    extra_plane = entry.runtime_data.planes[0]
    assert extra_plane.declination == 20
    assert extra_plane.azimuth == 160 - 180


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_retracks_home_location_on_update(
    hass: HomeAssistant,
) -> None:
    """Test HA's home location is used at setup and a changed value on refresh."""
    await hass.config.async_update(latitude=51.5, longitude=-0.1)
    entry = _config_entry(
        {CONF_DECLINATION: 30, CONF_AZIMUTH: 190, CONF_MODULES_POWER: 5100},
        entry_data={},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.forecast.latitude == 51.5

    await hass.config.async_update(latitude=48.85, longitude=2.35)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.forecast.latitude == 48.85
    assert coordinator.forecast.longitude == 2.35


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_coordinator_keeps_configured_angles_integral(
    hass: HomeAssistant,
) -> None:
    """Test fixed angles stay ints, so the request URL is unchanged for existing users."""
    entry = _config_entry(
        {CONF_DECLINATION: 30, CONF_AZIMUTH: 190, CONF_MODULES_POWER: 5100},
        entry_data=FIXED_LOCATION,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    forecast = entry.runtime_data.forecast
    assert isinstance(forecast.declination, int)
    assert isinstance(forecast.azimuth, int)
    assert f"{forecast.declination}/{forecast.azimuth}" == "30/10"
