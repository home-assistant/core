"""Test the Sofar Inverter Modbus switch platform."""

from unittest.mock import patch

from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sofar.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT, seed_pv_inverter

from tests.common import MockConfigEntry, snapshot_platform


async def _setup_pv(
    hass: HomeAssistant, *, remote_on: bool = False
) -> tuple[MockConfigEntry, MockModbusConnection]:
    """Set up a PV-only inverter with only the switch platform loaded."""
    connection = MockModbusConnection()
    seed_pv_inverter(connection.for_unit(1))
    if remote_on:
        connection.for_unit(1).holding[0x1104] = 1
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT, title=MOCK_MODEL
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.sofar.PLATFORMS", [Platform.SWITCH]),
        patch(
            "homeassistant.components.sofar.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: connection.for_unit(
                unit_id
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry, connection


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_pv_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the switch entities a PV-only inverter serves."""
    entry, _ = await _setup_pv(hass)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("remote_on", "service", "initial", "final"),
    [
        pytest.param(False, SERVICE_TURN_ON, STATE_OFF, STATE_ON, id="turn_on"),
        pytest.param(True, SERVICE_TURN_OFF, STATE_ON, STATE_OFF, id="turn_off"),
    ],
)
async def test_remote_switch_toggle(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    remote_on: bool,
    service: str,
    initial: str,
    final: str,
) -> None:
    """Test toggling the remote switch writes the register."""
    await _setup_pv(hass, remote_on=remote_on)
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_remote_switch_on_off"
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == initial

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == final


async def test_turn_on_modbus_error(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a write failure propagates as-is."""
    _, connection = await _setup_pv(hass)
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_remote_switch_on_off"
    )
    assert entity_id is not None
    connection.for_unit(1).fail_write(0x1104, ModbusError("busy"))

    with pytest.raises(ModbusError, match="busy"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
