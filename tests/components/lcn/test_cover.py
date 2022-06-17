"""Test for the LCN cover platform."""
from unittest.mock import patch

from pypck.inputs import ModStatusOutput, ModStatusRelays
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import MotorReverseTime, MotorStateModifier

from homeassistant.components.cover import DOMAIN as DOMAIN_COVER
from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er

from .conftest import MockModuleConnection


async def test_setup_lcn_cover(hass, entry, lcn_connection):
    """Test the setup of cover."""
    for entity_id in (
        "cover.cover_outputs",
        "cover.cover_relays",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OPEN


async def test_entity_attributes(hass, entry, lcn_connection):
    """Test the attributes of an entity."""
    entity_registry = er.async_get(hass)

    entity_outputs = entity_registry.async_get("cover.cover_outputs")

    assert entity_outputs
    assert entity_outputs.unique_id == f"{entry.entry_id}-m000007-outputs"
    assert entity_outputs.original_name == "Cover_Outputs"

    entity_relays = entity_registry.async_get("cover.cover_relays")

    assert entity_relays
    assert entity_relays.unique_id == f"{entry.entry_id}-m000007-motor1"
    assert entity_relays.original_name == "Cover_Relays"


@patch.object(MockModuleConnection, "control_motors_outputs")
async def test_outputs_open(control_motors_outputs, hass, lcn_connection):
    """Test the outputs cover opens."""
    state = hass.states.get("cover.cover_outputs")
    state.state = STATE_CLOSED

    # command failed
    control_motors_outputs.return_value = False

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.cover_outputs"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_outputs.assert_awaited_with(
        MotorStateModifier.UP, MotorReverseTime.RT1200
    )

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state != STATE_OPENING

    # command success
    control_motors_outputs.reset_mock(return_value=True)
    control_motors_outputs.return_value = True

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.cover_outputs"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_outputs.assert_awaited_with(
        MotorStateModifier.UP, MotorReverseTime.RT1200
    )

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state == STATE_OPENING


@patch.object(MockModuleConnection, "control_motors_outputs")
async def test_outputs_close(control_motors_outputs, hass, lcn_connection):
    """Test the outputs cover closes."""
    state = hass.states.get("cover.cover_outputs")
    state.state = STATE_OPEN

    # command failed
    control_motors_outputs.return_value = False

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.cover_outputs"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_outputs.assert_awaited_with(
        MotorStateModifier.DOWN, MotorReverseTime.RT1200
    )

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state != STATE_CLOSING

    # command success
    control_motors_outputs.reset_mock(return_value=True)
    control_motors_outputs.return_value = True

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.cover_outputs"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_outputs.assert_awaited_with(
        MotorStateModifier.DOWN, MotorReverseTime.RT1200
    )

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state == STATE_CLOSING


@patch.object(MockModuleConnection, "control_motors_outputs")
async def test_outputs_stop(control_motors_outputs, hass, lcn_connection):
    """Test the outputs cover stops."""
    state = hass.states.get("cover.cover_outputs")
    state.state = STATE_CLOSING

    # command failed
    control_motors_outputs.return_value = False

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.cover_outputs"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_outputs.assert_awaited_with(MotorStateModifier.STOP)

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state == STATE_CLOSING

    # command success
    control_motors_outputs.reset_mock(return_value=True)
    control_motors_outputs.return_value = True

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.cover_outputs"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_outputs.assert_awaited_with(MotorStateModifier.STOP)

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state not in (STATE_CLOSING, STATE_OPENING)


@patch.object(MockModuleConnection, "control_motors_relays")
async def test_relays_open(control_motors_relays, hass, lcn_connection):
    """Test the relays cover opens."""
    states = [MotorStateModifier.NOCHANGE] * 4
    states[0] = MotorStateModifier.UP

    state = hass.states.get("cover.cover_relays")
    state.state = STATE_CLOSED

    # command failed
    control_motors_relays.return_value = False

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.cover_relays"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_relays.assert_awaited_with(states)

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state != STATE_OPENING

    # command success
    control_motors_relays.reset_mock(return_value=True)
    control_motors_relays.return_value = True

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.cover_relays"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_relays.assert_awaited_with(states)

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state == STATE_OPENING


@patch.object(MockModuleConnection, "control_motors_relays")
async def test_relays_close(control_motors_relays, hass, lcn_connection):
    """Test the relays cover closes."""
    states = [MotorStateModifier.NOCHANGE] * 4
    states[0] = MotorStateModifier.DOWN

    state = hass.states.get("cover.cover_relays")
    state.state = STATE_OPEN

    # command failed
    control_motors_relays.return_value = False

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.cover_relays"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_relays.assert_awaited_with(states)

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state != STATE_CLOSING

    # command success
    control_motors_relays.reset_mock(return_value=True)
    control_motors_relays.return_value = True

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.cover_relays"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_relays.assert_awaited_with(states)

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state == STATE_CLOSING


@patch.object(MockModuleConnection, "control_motors_relays")
async def test_relays_stop(control_motors_relays, hass, lcn_connection):
    """Test the relays cover stops."""
    states = [MotorStateModifier.NOCHANGE] * 4
    states[0] = MotorStateModifier.STOP

    state = hass.states.get("cover.cover_relays")
    state.state = STATE_CLOSING

    # command failed
    control_motors_relays.return_value = False

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.cover_relays"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_relays.assert_awaited_with(states)

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state == STATE_CLOSING

    # command success
    control_motors_relays.reset_mock(return_value=True)
    control_motors_relays.return_value = True

    await hass.services.async_call(
        DOMAIN_COVER,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.cover_relays"},
        blocking=True,
    )
    await hass.async_block_till_done()
    control_motors_relays.assert_awaited_with(states)

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state not in (STATE_CLOSING, STATE_OPENING)


async def test_pushed_outputs_status_change(hass, entry, lcn_connection):
    """Test the outputs cover changes its state on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    state = hass.states.get("cover.cover_outputs")
    state.state = STATE_CLOSED

    # push status "open"
    input = ModStatusOutput(address, 0, 100)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state == STATE_OPENING

    # push status "stop"
    input = ModStatusOutput(address, 0, 0)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state not in (STATE_OPENING, STATE_CLOSING)

    # push status "close"
    input = ModStatusOutput(address, 1, 100)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("cover.cover_outputs")
    assert state is not None
    assert state.state == STATE_CLOSING


async def test_pushed_relays_status_change(hass, entry, lcn_connection):
    """Test the relays cover changes its state on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [False] * 8

    state = hass.states.get("cover.cover_relays")
    state.state = STATE_CLOSED

    # push status "open"
    states[0:2] = [True, False]
    input = ModStatusRelays(address, states)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state == STATE_OPENING

    # push status "stop"
    states[0] = False
    input = ModStatusRelays(address, states)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state not in (STATE_OPENING, STATE_CLOSING)

    # push status "close"
    states[0:2] = [True, True]
    input = ModStatusRelays(address, states)
    await device_connection.async_process_input(input)
    await hass.async_block_till_done()

    state = hass.states.get("cover.cover_relays")
    assert state is not None
    assert state.state == STATE_CLOSING


async def test_unload_config_entry(hass, entry, lcn_connection):
    """Test the cover is removed when the config entry is unloaded."""
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get("cover.cover_outputs").state == STATE_UNAVAILABLE
    assert hass.states.get("cover.cover_relays").state == STATE_UNAVAILABLE
