"""Test the Foreca sensor platform."""

import logging
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyforeca import (
    CurrentWeather,
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

OBSERVED_TEMPERATURE = "sensor.helsinki_observed_temperature"
PRECIPITATION_PROBABILITY = "sensor.helsinki_precipitation_probability"


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
    "observation",
    [
        pytest.param(None, id="no_station_nearby"),
        pytest.param(Observation(), id="empty_observation"),
    ],
)
async def test_sensors_without_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    observation: Observation | None,
) -> None:
    """Test sensors are unknown when the API leaves their value out."""
    mock_foreca_client.current.return_value = CurrentWeather()
    mock_foreca_client.observation_latest.return_value = observation
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    states = hass.states.async_all(Platform.SENSOR)
    assert len(states) == 15
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


async def test_failed_observation_leaves_other_entities_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing observation request makes only its sensors unavailable.

    The failure and the recovery are each logged once, however many updates
    the failure lasts.
    """
    caplog.set_level(logging.INFO, logger="homeassistant.components.foreca")
    mock_foreca_client.observation_latest.side_effect = ForecaConnectionError("Timeout")
    await init_integration(hass, mock_config_entry)

    assert hass.states.get(OBSERVED_TEMPERATURE).state == STATE_UNAVAILABLE
    assert hass.states.get(PRECIPITATION_PROBABILITY).state == "5"
    assert hass.states.get("weather.helsinki").state == "partlycloudy"

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(OBSERVED_TEMPERATURE).state == STATE_UNAVAILABLE

    mock_foreca_client.observation_latest.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(OBSERVED_TEMPERATURE).state == "8"
    assert mock_foreca_client.observation_latest.await_count == 3
    assert [
        (record.levelno, record.getMessage())
        for record in caplog.records
        if record.name == "homeassistant.components.foreca.coordinator"
        and record.levelno >= logging.INFO
    ] == [
        (logging.INFO, "Error fetching foreca Helsinki observation data: Timeout"),
        (logging.INFO, "Fetching foreca Helsinki observation data recovered"),
    ]


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
