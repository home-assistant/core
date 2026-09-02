"""Tests for the Besen sensor platform."""

from unittest.mock import Mock

from besen.models import ChargeStatus
import pytest
from syrupy.assertion import SnapshotAssertion

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
        f"{mock_besen_client.address}_l1_current",
        f"{mock_besen_client.address}_l1_voltage",
        f"{mock_besen_client.address}_l2_current",
        f"{mock_besen_client.address}_l2_voltage",
        f"{mock_besen_client.address}_l3_current",
        f"{mock_besen_client.address}_l3_voltage",
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
