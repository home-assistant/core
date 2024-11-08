"""Test for the LCN binary sensor platform."""

from unittest.mock import patch

from pypck.inputs import ModStatusBinSensors, ModStatusKeyLocks, ModStatusVar
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import Var, VarValue
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.lcn import DOMAIN
from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MockConfigEntry, init_integration

from tests.common import snapshot_platform

BINARY_SENSOR_LOCKREGULATOR1 = "binary_sensor.sensor_lockregulator1"
BINARY_SENSOR_SENSOR1 = "binary_sensor.binary_sensor1"
BINARY_SENSOR_KEYLOCK = "binary_sensor.sensor_keylock"


async def test_setup_lcn_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the setup of binary sensor."""
    with patch("homeassistant.components.lcn.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_pushed_lock_setpoint_status_change(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test the lock setpoint sensor changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    # push status lock setpoint
    inp = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x8000))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_LOCKREGULATOR1)
    assert state is not None
    assert state.state == STATE_ON

    # push status unlock setpoint
    inp = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x7FFF))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_LOCKREGULATOR1)
    assert state is not None
    assert state.state == STATE_OFF


async def test_pushed_binsensor_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the binary port sensor changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [False] * 8

    # push status binary port "off"
    inp = ModStatusBinSensors(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_SENSOR1)
    assert state is not None
    assert state.state == STATE_OFF

    # push status binary port "on"
    states[0] = True
    inp = ModStatusBinSensors(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_SENSOR1)
    assert state is not None
    assert state.state == STATE_ON


async def test_pushed_keylock_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the keylock sensor changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [[False] * 8 for i in range(4)]

    # push status keylock "off"
    inp = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_KEYLOCK)
    assert state is not None
    assert state.state == STATE_OFF

    # push status keylock "on"
    states[0][4] = True
    inp = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_KEYLOCK)
    assert state is not None
    assert state.state == STATE_ON


async def test_unload_config_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the binary sensor is removed when the config entry is unloaded."""
    await init_integration(hass, entry)

    await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(BINARY_SENSOR_LOCKREGULATOR1).state == STATE_UNAVAILABLE
    assert hass.states.get(BINARY_SENSOR_SENSOR1).state == STATE_UNAVAILABLE
    assert hass.states.get(BINARY_SENSOR_KEYLOCK).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "entity_id", ["binary_sensor.sensor_lockregulator1", "binary_sensor.sensor_keylock"]
)
async def test_create_issue(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    issue_registry: ir.IssueRegistry,
    entry: MockConfigEntry,
    entity_id,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {"action": "test.automation"},
            }
        },
    )

    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test": {
                    "sequence": {
                        "condition": "state",
                        "entity_id": entity_id,
                        "state": STATE_ON,
                    }
                }
            }
        },
    )

    await init_integration(hass, entry)

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_binary_sensor_{entity_id}"
    )

    assert len(issue_registry.issues) == 1
