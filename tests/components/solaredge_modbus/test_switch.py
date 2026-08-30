"""Tests for the SolarEdge Modbus switch entities."""

from unittest.mock import patch

from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

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

from tests.common import MockConfigEntry, snapshot_platform

EXTERNAL_PRODUCTION_ENTITY = "switch.solaredge_se10000h_external_production"
NEGATIVE_SITE_LIMIT_ENTITY = "switch.solaredge_se10000h_negative_site_limit"

# The export mode register, which carries both flags and reads as absent when
# the whole block is.
EXPORT_MODE_REGISTER = 57344


async def _setup_switch_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch(
        "homeassistant.components.solaredge_modbus.PLATFORMS", [Platform.SWITCH]
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All switch entities and their states match the snapshot."""
    await _setup_switch_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switches_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Export-control flags are installer settings, not day-to-day switches."""
    await _setup_switch_platform(hass, mock_config_entry)

    for entity_id in (
        EXTERNAL_PRODUCTION_ENTITY,
        "switch.solaredge_se10000h_negative_site_limit",
    ):
        assert hass.states.get(entity_id) is None
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_no_switches_without_export_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """An inverter without the export control block gets no switches.

    Both switches are flags in that block, so there is nothing to show for an
    installation that does not have it.
    """
    # A real device answers reads of a block it does not have with a Modbus
    # exception (illegal data address).
    mock_modbus_unit.fail_read(EXPORT_MODE_REGISTER, IllegalDataAddressError())

    await _setup_switch_platform(hass, mock_config_entry)

    assert hass.states.async_entity_ids(SWITCH_DOMAIN) == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "bit"),
    [
        pytest.param(EXTERNAL_PRODUCTION_ENTITY, 10, id="external production"),
        pytest.param(NEGATIVE_SITE_LIMIT_ENTITY, 11, id="negative site limit"),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    entity_id: str,
    bit: int,
) -> None:
    """Turning a switch on and off writes its own flag bit to the device.

    Both flags live in the export mode register, each with a bit and a setter
    of its own, so each has to reach the one it names.
    """
    await _setup_switch_platform(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert mock_modbus_unit.holding[EXPORT_MODE_REGISTER] & (1 << bit)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not mock_modbus_unit.holding[EXPORT_MODE_REGISTER] & (1 << bit)
