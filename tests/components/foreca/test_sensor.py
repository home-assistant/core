"""Test the Foreca sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyforeca import (
    AirQualityForecast,
    CurrentWeather,
    ForecaAuthError,
    ForecaConnectionError,
    ForecaProductUnavailableError,
    Observation,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.foreca.const import UPDATE_INTERVAL, symbol_to_condition
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import init_integration

AIR_QUALITY_INDEX = "sensor.helsinki_air_quality_index"
OBSERVED_TEMPERATURE = "sensor.helsinki_observed_temperature"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_foreca_client")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the states of the sensors."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_foreca_client")
async def test_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test which sensors are disabled by default."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    disabled = {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    }
    assert disabled == {
        "sensor.helsinki_carbon_monoxide_index",
        "sensor.helsinki_nitrogen_dioxide_index",
        "sensor.helsinki_ozone_index",
        "sensor.helsinki_pm10_index",
        "sensor.helsinki_pm2_5_index",
        "sensor.helsinki_sulphur_dioxide_index",
        "sensor.helsinki_observation_time",
        "sensor.helsinki_observed_apparent_temperature",
        "sensor.helsinki_observed_condition",
        "sensor.helsinki_observed_pressure",
        "sensor.helsinki_observed_snow_depth",
        "sensor.helsinki_observed_visibility",
        "sensor.helsinki_observed_wind_direction",
        "sensor.helsinki_observed_wind_gust_speed",
        "sensor.helsinki_observed_wind_speed",
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("observation", "air_quality"),
    [
        pytest.param(None, [], id="no_station_or_air_quality_nearby"),
        pytest.param(Observation(), [AirQualityForecast()], id="empty_values"),
    ],
)
async def test_sensors_without_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    observation: Observation | None,
    air_quality: list[AirQualityForecast],
) -> None:
    """Test sensors are unknown when the API leaves their value out."""
    mock_foreca_client.current.return_value = CurrentWeather()
    mock_foreca_client.observation_latest.return_value = observation
    mock_foreca_client.air_quality_hourly.return_value = air_quality
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    states = hass.states.async_all(Platform.SENSOR)
    assert len(states) == 23
    assert {state.state for state in states} == {STATE_UNKNOWN}


@pytest.mark.usefixtures("mock_foreca_client", "entity_registry_enabled_by_default")
async def test_observed_condition_options_cover_every_symbol(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test every Foreca symbol maps to one of the observed condition's options."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.helsinki_observed_condition")
    assert state is not None
    codes = [
        f"{day}{cloudiness}{rate}{kind}"
        for day in "dn"
        for cloudiness in range(7)
        for rate in range(5)
        for kind in range(3)
    ]
    assert {symbol_to_condition(code) for code in codes} <= set(
        state.attributes["options"]
    )


@pytest.mark.usefixtures("mock_foreca_client", "entity_registry_enabled_by_default")
async def test_observed_visibility_in_miles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test observed visibility follows a US customary unit system."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.helsinki_observed_visibility")
    assert state is not None
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILES
    assert float(state.state) == pytest.approx(12.43, abs=0.01)


def _unavailable(hass: HomeAssistant) -> set[str]:
    """Return the entities that are unavailable."""
    return {
        state.entity_id
        for state in hass.states.async_all()
        if state.state == STATE_UNAVAILABLE
    }


@pytest.mark.parametrize(
    ("method", "unavailable"),
    [
        pytest.param(
            "observation_latest",
            {
                "sensor.helsinki_observation_station",
                "sensor.helsinki_observed_humidity",
                OBSERVED_TEMPERATURE,
            },
            id="observation",
        ),
        pytest.param(
            "air_quality_hourly",
            {AIR_QUALITY_INDEX, "sensor.helsinki_dominant_pollutant"},
            id="air_quality",
        ),
    ],
)
async def test_failed_request_leaves_other_entities_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    unavailable: set[str],
) -> None:
    """Test a failing station or air quality request makes only its sensors unavailable."""
    getattr(mock_foreca_client, method).side_effect = ForecaConnectionError("Timeout")
    await init_integration(hass, mock_config_entry)

    assert _unavailable(hass) == unavailable

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _unavailable(hass) == unavailable

    getattr(mock_foreca_client, method).side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _unavailable(hass) == set()
    assert getattr(mock_foreca_client, method).await_count == 3


async def test_air_quality_update_error_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing air quality request logs the translated error."""
    mock_foreca_client.air_quality_hourly.side_effect = ForecaConnectionError("Timeout")
    await init_integration(hass, mock_config_entry)

    assert "Error fetching the air quality" in caplog.text


@pytest.mark.parametrize(
    ("method", "entity_id", "value"),
    [
        pytest.param("observation_latest", OBSERVED_TEMPERATURE, "8", id="observation"),
        pytest.param("air_quality_hourly", AIR_QUALITY_INDEX, "31", id="air_quality"),
    ],
)
async def test_rejected_key_on_a_sensor_request_keeps_the_entry_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    entity_id: str,
    value: str,
) -> None:
    """Test a key rejected only by a sensor request leaves the rest running.

    The request keeps being polled, so its sensors recover once the API
    accepts it again.
    """
    await init_integration(hass, mock_config_entry)

    getattr(mock_foreca_client, method).side_effect = ForecaAuthError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get("weather.helsinki").state == "partlycloudy"

    getattr(mock_foreca_client, method).side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == value


async def test_observations_missing_from_plan_keep_the_entry_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a plan without station observations loads and asks for no new key."""
    mock_foreca_client.observation_latest.side_effect = ForecaProductUnavailableError
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.flow.async_progress() == []
    assert hass.states.get(OBSERVED_TEMPERATURE).state == STATE_UNAVAILABLE
    assert hass.states.get("weather.helsinki").state == "partlycloudy"


async def test_unknown_pollutant(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a pollutant name outside the documented set reads as unknown."""
    mock_foreca_client.air_quality_hourly.return_value = [
        AirQualityForecast(pollutant="Pollen", aqi=12)
    ]
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.helsinki_dominant_pollutant").state == STATE_UNKNOWN
    assert hass.states.get(AIR_QUALITY_INDEX).state == "12"
