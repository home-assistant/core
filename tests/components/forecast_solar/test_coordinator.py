"""Test the Forecast.Solar coordinator."""

from typing import Any
from unittest.mock import MagicMock

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

from tests.common import MockConfigEntry

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


@pytest.mark.parametrize(
    "state",
    [
        pytest.param("unavailable", id="unavailable"),
        pytest.param("unknown", id="unknown"),
        pytest.param("north", id="not_a_number"),
        pytest.param("500", id="above_range"),
    ],
)
async def test_coordinator_uses_last_reading_while_sensor_unreadable(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
    caplog: pytest.LogCaptureFixture,
    state: str,
) -> None:
    """Test an unreadable sensor keeps its last reading, so the forecast stays up."""
    hass.states.async_set(AZIMUTH_SENSOR, "100", DEGREES)
    entry = _config_entry(AZIMUTH_SENSOR_PLANE, entry_data=FIXED_LOCATION)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    estimate_calls = mock_forecast_solar.estimate.call_count

    hass.states.async_set(AZIMUTH_SENSOR, state, DEGREES)
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.forecast.azimuth == 100 - 180
    assert mock_forecast_solar.estimate.call_count == estimate_calls + 2
    # Logged once while unreadable, not on every update.
    assert caplog.text.count(f"Sensor {AZIMUTH_SENSOR} can't be read") == 1

    hass.states.async_set(AZIMUTH_SENSOR, "200", DEGREES)
    await coordinator.async_refresh()

    assert coordinator.forecast.azimuth == 200 - 180
    assert f"Sensor {AZIMUTH_SENSOR} can be read again" in caplog.text


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

    extra_plane = entry.runtime_data.forecast.planes[0]
    assert extra_plane.declination == 20
    assert extra_plane.azimuth == 160 - 180


@pytest.mark.parametrize(
    ("entry_data", "core_configs", "location", "extra_calls"),
    [
        pytest.param(
            {},
            [{"latitude": 48.85, "longitude": 2.35}],
            (48.85, 2.35),
            1,
            id="home_moved",
        ),
        pytest.param(
            {},
            [{"latitude": 48.0 + index / 100, "longitude": 2.35} for index in range(5)],
            (48.0, 2.35),
            1,
            id="home_moves_often",
        ),
        pytest.param({}, [{"currency": "USD"}], (51.5, -0.1), 0, id="home_unchanged"),
        pytest.param(
            FIXED_LOCATION,
            [{"latitude": 48.85, "longitude": 2.35}],
            (52.42, 4.42),
            0,
            id="fixed_location",
        ),
    ],
)
async def test_coordinator_follows_home_location(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
    entry_data: dict[str, Any],
    core_configs: list[dict[str, Any]],
    location: tuple[float, float],
    extra_calls: int,
) -> None:
    """Test an entry following HA's location refreshes when it moves, throttled."""
    await hass.config.async_update(latitude=51.5, longitude=-0.1)
    entry = _config_entry(
        {CONF_DECLINATION: 30, CONF_AZIMUTH: 190, CONF_MODULES_POWER: 5100},
        entry_data=entry_data,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    estimate_calls = mock_forecast_solar.estimate.call_count

    for core_config in core_configs:
        await hass.config.async_update(**core_config)
        await hass.async_block_till_done()

    forecast = entry.runtime_data.forecast
    assert (forecast.latitude, forecast.longitude) == location
    assert mock_forecast_solar.estimate.call_count == estimate_calls + extra_calls


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
