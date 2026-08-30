"""Tests for the Besen sensor platform."""

from unittest.mock import Mock

from besen.const import (
    CHARGING_STATUS,
    CHARGING_STATUS_DESCRIPTIONS,
    CURRENT_STATE,
    ERRORS,
    OUTPUT_STATE,
    PLUG_STATE,
)
from besen.models import ChargeStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.besen.sensor import (
    CHARGING_MESSAGES,
    CHARGING_STATES,
    CURRENT_STATES,
    ERROR_STATES,
    OUTPUT_STATES,
    PLUG_STATES,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import publish_besen_state
from .conftest import charger_state, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

POWER_ENTITY_ID = "sensor.garage_charging_power"
CHARGING_STATUS_ENTITY_ID = "sensor.garage_charging_status"
CHARGING_MESSAGE_ENTITY_ID = "sensor.garage_charging_message"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("phases", [1, 3], ids=["single_phase", "three_phase"])
async def test_sensor_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    phases: int,
) -> None:
    """Test sensor states and registry data."""

    mock_besen_client.state = charger_state(phases=phases)
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_besen_client.async_start.assert_awaited_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_updates_from_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test sensor states update from client push data."""

    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    publish_besen_state(
        mock_besen_client,
        charger_state(
            charge=ChargeStatus(
                error_details="Emergency Stop",
                charging_status="Fault",
                charging_status_description="See Error State",
                plug_state="Disconnected",
                output_state="Idle",
                current_state="Ready to charge",
                power=7200,
                total_energy=123.45,
                session_energy=4.56,
                inner_temp_c=26.5,
            )
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(POWER_ENTITY_ID)) is not None
    assert state.state == "7200"
    assert (state := hass.states.get("sensor.garage_total_energy")) is not None
    assert state.state == "123.45"
    assert (state := hass.states.get("sensor.garage_session_energy")) is not None
    assert state.state == "4.56"
    assert (state := hass.states.get("sensor.garage_internal_temperature")) is not None
    assert state.state == "26.5"
    assert (state := hass.states.get(CHARGING_STATUS_ENTITY_ID)) is not None
    assert state.state == "fault"
    assert (state := hass.states.get(CHARGING_MESSAGE_ENTITY_ID)) is not None
    assert state.state == "see_error_state"
    assert (state := hass.states.get("sensor.garage_error_state")) is not None
    assert state.state == "emergency_stop"
    assert (state := hass.states.get("sensor.garage_plug_state")) is not None
    assert state.state == "disconnected"
    assert (state := hass.states.get("sensor.garage_output_state")) is not None
    assert state.state == "idle"
    assert (state := hass.states.get("sensor.garage_current_state")) is not None
    assert state.state == "ready_to_charge"


async def test_sensor_unknown_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test a missing measurement is unknown while the charger is available."""

    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    publish_besen_state(mock_besen_client, charger_state(charge=ChargeStatus()))
    await hass.async_block_till_done()

    assert (state := hass.states.get(POWER_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get(CHARGING_STATUS_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get(CHARGING_MESSAGE_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_enum_sensors_unknown_for_unsupported_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test unsupported protocol values are exposed as unknown."""

    mock_besen_client.state = charger_state(
        charge=ChargeStatus(
            error_details="Unexpected",
            charging_status="Unexpected",
            charging_status_description="Unexpected",
            plug_state="Unexpected",
            output_state="Unexpected",
            current_state="Unexpected",
        )
    )

    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id in (
        CHARGING_STATUS_ENTITY_ID,
        CHARGING_MESSAGE_ENTITY_ID,
        "sensor.garage_error_state",
        "sensor.garage_plug_state",
        "sensor.garage_output_state",
        "sensor.garage_current_state",
    ):
        assert (state := hass.states.get(entity_id)) is not None
        assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("available", "authenticated"),
    [
        (False, True),
        (True, False),
    ],
)
async def test_sensor_unavailable_from_client_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    available: bool,
    authenticated: bool,
) -> None:
    """Test sensor availability follows client connection and authentication."""

    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    publish_besen_state(
        mock_besen_client,
        charger_state(available=available, authenticated=authenticated),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(POWER_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE


async def test_diagnostic_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test diagnostic sensors are disabled by default."""

    mock_besen_client.state = charger_state(phases=3)
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    diagnostic_entries = {
        entry.unique_id: entry
        for entry in entries
        if entry.entity_category is EntityCategory.DIAGNOSTIC
    }
    assert set(diagnostic_entries) == {
        f"{mock_besen_client.address}_external_temperature",
        f"{mock_besen_client.address}_error_state",
        f"{mock_besen_client.address}_current_state",
        f"{mock_besen_client.address}_l1_current",
        f"{mock_besen_client.address}_l1_voltage",
        f"{mock_besen_client.address}_l2_current",
        f"{mock_besen_client.address}_l2_voltage",
        f"{mock_besen_client.address}_l3_current",
        f"{mock_besen_client.address}_l3_voltage",
        f"{mock_besen_client.address}_output_state",
        f"{mock_besen_client.address}_plug_state",
    }
    for entry in diagnostic_entries.values():
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entry.entity_id) is None


@pytest.mark.parametrize(("phases", "expected"), [(1, False), (3, True)])
async def test_three_phase_sensor_filtering(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    phases: int,
    expected: bool,
) -> None:
    """Test L2 and L3 sensors are added only for three-phase chargers."""

    mock_besen_client.state = charger_state(phases=phases)
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    three_phase_unique_ids = {
        f"{mock_besen_client.address}_l2_voltage",
        f"{mock_besen_client.address}_l2_current",
        f"{mock_besen_client.address}_l3_voltage",
        f"{mock_besen_client.address}_l3_current",
    }
    assert three_phase_unique_ids.issubset(unique_ids) is expected


def test_enum_sensor_options_cover_library_states() -> None:
    """Test every library state has a stable Home Assistant option."""

    assert set(ERROR_STATES) == set(ERRORS.values())
    assert set(CHARGING_STATES) == set(CHARGING_STATUS.values())
    assert set(CHARGING_MESSAGES) == set(CHARGING_STATUS_DESCRIPTIONS.values())
    assert set(PLUG_STATES) == set(PLUG_STATE)
    assert set(OUTPUT_STATES) == set(OUTPUT_STATE)
    assert set(CURRENT_STATES) == set(CURRENT_STATE)
