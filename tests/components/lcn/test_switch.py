"""Test for the LCN switch platform."""

from unittest.mock import patch

from pypck.inputs import (
    ModStatusKeyLocks,
    ModStatusOutput,
    ModStatusRelays,
    ModStatusVar,
)
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import KeyLockStateModifier, RelayStateModifier, Var, VarValue
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockConfigEntry, MockModuleConnection, init_integration

from tests.common import snapshot_platform

SWITCH_OUTPUT1 = "switch.testmodule_switch_output1"
SWITCH_OUTPUT2 = "switch.testmodule_switch_output2"
SWITCH_RELAY1 = "switch.testmodule_switch_relay1"
SWITCH_RELAY2 = "switch.testmodule_switch_relay2"
SWITCH_REGULATOR1 = "switch.testmodule_switch_regulator1"
SWITCH_KEYLOCKK1 = "switch.testmodule_switch_keylock1"


async def test_setup_lcn_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the setup of switch."""
    with patch("homeassistant.components.lcn.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_output_turn_on(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the output switch turns on."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "dim_output") as dim_output:
        # command failed
        dim_output.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_OUTPUT1},
            blocking=True,
        )

        dim_output.assert_awaited_with(0, 100, 0)

        state = hass.states.get(SWITCH_OUTPUT1)
        assert state.state == STATE_OFF

        # command success
        dim_output.reset_mock(return_value=True)
        dim_output.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_OUTPUT1},
            blocking=True,
        )

        dim_output.assert_awaited_with(0, 100, 0)

        state = hass.states.get(SWITCH_OUTPUT1)
        assert state.state == STATE_ON


async def test_output_turn_off(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the output switch turns off."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "dim_output") as dim_output:
        state = hass.states.get(SWITCH_OUTPUT1)
        state.state = STATE_ON

        # command failed
        dim_output.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_OUTPUT1},
            blocking=True,
        )

        dim_output.assert_awaited_with(0, 0, 0)

        state = hass.states.get(SWITCH_OUTPUT1)
        assert state.state == STATE_ON

        # command success
        dim_output.reset_mock(return_value=True)
        dim_output.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_OUTPUT1},
            blocking=True,
        )

        dim_output.assert_awaited_with(0, 0, 0)

        state = hass.states.get(SWITCH_OUTPUT1)
        assert state.state == STATE_OFF


async def test_relay_turn_on(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the relay switch turns on."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "control_relays") as control_relays:
        states = [RelayStateModifier.NOCHANGE] * 8
        states[0] = RelayStateModifier.ON

        # command failed
        control_relays.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_RELAY1},
            blocking=True,
        )

        control_relays.assert_awaited_with(states)

        state = hass.states.get(SWITCH_RELAY1)
        assert state.state == STATE_OFF

        # command success
        control_relays.reset_mock(return_value=True)
        control_relays.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_RELAY1},
            blocking=True,
        )

        control_relays.assert_awaited_with(states)

        state = hass.states.get(SWITCH_RELAY1)
        assert state.state == STATE_ON


async def test_relay_turn_off(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the relay switch turns off."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "control_relays") as control_relays:
        states = [RelayStateModifier.NOCHANGE] * 8
        states[0] = RelayStateModifier.OFF

        state = hass.states.get(SWITCH_RELAY1)
        state.state = STATE_ON

        # command failed
        control_relays.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_RELAY1},
            blocking=True,
        )

        control_relays.assert_awaited_with(states)

        state = hass.states.get(SWITCH_RELAY1)
        assert state.state == STATE_ON

        # command success
        control_relays.reset_mock(return_value=True)
        control_relays.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_RELAY1},
            blocking=True,
        )

        control_relays.assert_awaited_with(states)

        state = hass.states.get(SWITCH_RELAY1)
        assert state.state == STATE_OFF


async def test_regulatorlock_turn_on(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the regulator lock switch turns on."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_regulator") as lock_regulator:
        # command failed
        lock_regulator.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_REGULATOR1},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, True)

        state = hass.states.get(SWITCH_REGULATOR1)
        assert state.state == STATE_OFF

        # command success
        lock_regulator.reset_mock(return_value=True)
        lock_regulator.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_REGULATOR1},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, True)

        state = hass.states.get(SWITCH_REGULATOR1)
        assert state.state == STATE_ON


async def test_regulatorlock_turn_off(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the regulator lock switch turns off."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_regulator") as lock_regulator:
        state = hass.states.get(SWITCH_REGULATOR1)
        state.state = STATE_ON

        # command failed
        lock_regulator.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_REGULATOR1},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, False)

        state = hass.states.get(SWITCH_REGULATOR1)
        assert state.state == STATE_ON

        # command success
        lock_regulator.reset_mock(return_value=True)
        lock_regulator.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_REGULATOR1},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, False)

        state = hass.states.get(SWITCH_REGULATOR1)
        assert state.state == STATE_OFF


async def test_keylock_turn_on(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the keylock switch turns on."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_keys") as lock_keys:
        states = [KeyLockStateModifier.NOCHANGE] * 8
        states[0] = KeyLockStateModifier.ON

        # command failed
        lock_keys.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_KEYLOCKK1},
            blocking=True,
        )

        lock_keys.assert_awaited_with(0, states)

        state = hass.states.get(SWITCH_KEYLOCKK1)
        assert state.state == STATE_OFF

        # command success
        lock_keys.reset_mock(return_value=True)
        lock_keys.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_KEYLOCKK1},
            blocking=True,
        )

        lock_keys.assert_awaited_with(0, states)

        state = hass.states.get(SWITCH_KEYLOCKK1)
        assert state.state == STATE_ON


async def test_keylock_turn_off(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the keylock switch turns off."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_keys") as lock_keys:
        states = [KeyLockStateModifier.NOCHANGE] * 8
        states[0] = KeyLockStateModifier.OFF

        state = hass.states.get(SWITCH_KEYLOCKK1)
        state.state = STATE_ON

        # command failed
        lock_keys.return_value = False

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_KEYLOCKK1},
            blocking=True,
        )

        lock_keys.assert_awaited_with(0, states)

        state = hass.states.get(SWITCH_KEYLOCKK1)
        assert state.state == STATE_ON

        # command success
        lock_keys.reset_mock(return_value=True)
        lock_keys.return_value = True

        await hass.services.async_call(
            DOMAIN_SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_KEYLOCKK1},
            blocking=True,
        )

        lock_keys.assert_awaited_with(0, states)

        state = hass.states.get(SWITCH_KEYLOCKK1)
        assert state.state == STATE_OFF


async def test_pushed_output_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the output switch changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    # push status "on"
    inp = ModStatusOutput(address, 0, 100)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_OUTPUT1)
    assert state.state == STATE_ON

    # push status "off"
    inp = ModStatusOutput(address, 0, 0)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_OUTPUT1)
    assert state.state == STATE_OFF


async def test_pushed_relay_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the relay switch changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [False] * 8

    # push status "on"
    states[0] = True
    inp = ModStatusRelays(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_RELAY1)
    assert state.state == STATE_ON

    # push status "off"
    states[0] = False
    inp = ModStatusRelays(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_RELAY1)
    assert state.state == STATE_OFF


async def test_pushed_regulatorlock_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the regulator lock switch changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [False] * 8

    # push status "on"
    states[0] = True
    inp = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x8000))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_REGULATOR1)
    assert state.state == STATE_ON

    # push status "off"
    states[0] = False
    inp = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x7FFF))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_REGULATOR1)
    assert state.state == STATE_OFF


async def test_pushed_keylock_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the keylock switch changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [[False] * 8 for i in range(4)]
    states[0][0] = True

    # push status "on"
    inp = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_KEYLOCKK1)
    assert state.state == STATE_ON

    # push status "off"
    states[0][0] = False
    inp = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_KEYLOCKK1)
    assert state.state == STATE_OFF


async def test_unload_config_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the switch is removed when the config entry is unloaded."""
    await init_integration(hass, entry)

    await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(SWITCH_OUTPUT1).state == STATE_UNAVAILABLE
