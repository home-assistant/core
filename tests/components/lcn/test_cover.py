"""Test for the LCN cover platform."""

from unittest.mock import patch

from pypck.inputs import ModStatusOutput, ModStatusRelays
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import MotorReverseTime, MotorStateModifier
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import DOMAIN as DOMAIN_COVER, CoverState
from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockConfigEntry, MockModuleConnection, init_integration

from tests.common import snapshot_platform

COVER_OUTPUTS = "cover.cover_outputs"
COVER_RELAYS = "cover.cover_relays"


async def test_setup_lcn_cover(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the setup of cover."""
    with patch("homeassistant.components.lcn.PLATFORMS", [Platform.COVER]):
        await init_integration(hass, entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_outputs_open(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the outputs cover opens."""
    await init_integration(hass, entry)

    with patch.object(
        MockModuleConnection, "control_motors_outputs"
    ) as control_motors_outputs:
        state = hass.states.get(COVER_OUTPUTS)
        state.state = CoverState.CLOSED

        # command failed
        control_motors_outputs.return_value = False

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: COVER_OUTPUTS},
            blocking=True,
        )

        control_motors_outputs.assert_awaited_with(
            MotorStateModifier.UP, MotorReverseTime.RT1200
        )

        state = hass.states.get(COVER_OUTPUTS)
        assert state is not None
        assert state.state != CoverState.OPENING

        # command success
        control_motors_outputs.reset_mock(return_value=True)
        control_motors_outputs.return_value = True

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: COVER_OUTPUTS},
            blocking=True,
        )

        control_motors_outputs.assert_awaited_with(
            MotorStateModifier.UP, MotorReverseTime.RT1200
        )

        state = hass.states.get(COVER_OUTPUTS)
        assert state is not None
        assert state.state == CoverState.OPENING


async def test_outputs_close(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the outputs cover closes."""
    await init_integration(hass, entry)

    with patch.object(
        MockModuleConnection, "control_motors_outputs"
    ) as control_motors_outputs:
        state = hass.states.get(COVER_OUTPUTS)
        state.state = CoverState.OPEN

        # command failed
        control_motors_outputs.return_value = False

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: COVER_OUTPUTS},
            blocking=True,
        )

        control_motors_outputs.assert_awaited_with(
            MotorStateModifier.DOWN, MotorReverseTime.RT1200
        )

        state = hass.states.get(COVER_OUTPUTS)
        assert state is not None
        assert state.state != CoverState.CLOSING

        # command success
        control_motors_outputs.reset_mock(return_value=True)
        control_motors_outputs.return_value = True

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: COVER_OUTPUTS},
            blocking=True,
        )

        control_motors_outputs.assert_awaited_with(
            MotorStateModifier.DOWN, MotorReverseTime.RT1200
        )

        state = hass.states.get(COVER_OUTPUTS)
        assert state is not None
        assert state.state == CoverState.CLOSING


async def test_outputs_stop(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the outputs cover stops."""
    await init_integration(hass, entry)

    with patch.object(
        MockModuleConnection, "control_motors_outputs"
    ) as control_motors_outputs:
        state = hass.states.get(COVER_OUTPUTS)
        state.state = CoverState.CLOSING

        # command failed
        control_motors_outputs.return_value = False

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: COVER_OUTPUTS},
            blocking=True,
        )

        control_motors_outputs.assert_awaited_with(MotorStateModifier.STOP)

        state = hass.states.get(COVER_OUTPUTS)
        assert state is not None
        assert state.state == CoverState.CLOSING

        # command success
        control_motors_outputs.reset_mock(return_value=True)
        control_motors_outputs.return_value = True

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: COVER_OUTPUTS},
            blocking=True,
        )

        control_motors_outputs.assert_awaited_with(MotorStateModifier.STOP)

        state = hass.states.get(COVER_OUTPUTS)
        assert state is not None
        assert state.state not in (CoverState.CLOSING, CoverState.OPENING)


async def test_relays_open(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the relays cover opens."""
    await init_integration(hass, entry)

    with patch.object(
        MockModuleConnection, "control_motors_relays"
    ) as control_motors_relays:
        states = [MotorStateModifier.NOCHANGE] * 4
        states[0] = MotorStateModifier.UP

        state = hass.states.get(COVER_RELAYS)
        state.state = CoverState.CLOSED

        # command failed
        control_motors_relays.return_value = False

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: COVER_RELAYS},
            blocking=True,
        )

        control_motors_relays.assert_awaited_with(states)

        state = hass.states.get(COVER_RELAYS)
        assert state is not None
        assert state.state != CoverState.OPENING

        # command success
        control_motors_relays.reset_mock(return_value=True)
        control_motors_relays.return_value = True

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: COVER_RELAYS},
            blocking=True,
        )

        control_motors_relays.assert_awaited_with(states)

        state = hass.states.get(COVER_RELAYS)
        assert state is not None
        assert state.state == CoverState.OPENING


async def test_relays_close(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the relays cover closes."""
    await init_integration(hass, entry)

    with patch.object(
        MockModuleConnection, "control_motors_relays"
    ) as control_motors_relays:
        states = [MotorStateModifier.NOCHANGE] * 4
        states[0] = MotorStateModifier.DOWN

        state = hass.states.get(COVER_RELAYS)
        state.state = CoverState.OPEN

        # command failed
        control_motors_relays.return_value = False

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: COVER_RELAYS},
            blocking=True,
        )

        control_motors_relays.assert_awaited_with(states)

        state = hass.states.get(COVER_RELAYS)
        assert state is not None
        assert state.state != CoverState.CLOSING

        # command success
        control_motors_relays.reset_mock(return_value=True)
        control_motors_relays.return_value = True

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: COVER_RELAYS},
            blocking=True,
        )

        control_motors_relays.assert_awaited_with(states)

        state = hass.states.get(COVER_RELAYS)
        assert state is not None
        assert state.state == CoverState.CLOSING


async def test_relays_stop(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the relays cover stops."""
    await init_integration(hass, entry)

    with patch.object(
        MockModuleConnection, "control_motors_relays"
    ) as control_motors_relays:
        states = [MotorStateModifier.NOCHANGE] * 4
        states[0] = MotorStateModifier.STOP

        state = hass.states.get(COVER_RELAYS)
        state.state = CoverState.CLOSING

        # command failed
        control_motors_relays.return_value = False

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: COVER_RELAYS},
            blocking=True,
        )

        control_motors_relays.assert_awaited_with(states)

        state = hass.states.get(COVER_RELAYS)
        assert state is not None
        assert state.state == CoverState.CLOSING

        # command success
        control_motors_relays.reset_mock(return_value=True)
        control_motors_relays.return_value = True

        await hass.services.async_call(
            DOMAIN_COVER,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: COVER_RELAYS},
            blocking=True,
        )

        control_motors_relays.assert_awaited_with(states)

        state = hass.states.get(COVER_RELAYS)
        assert state is not None
        assert state.state not in (CoverState.CLOSING, CoverState.OPENING)


async def test_pushed_outputs_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the outputs cover changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    state = hass.states.get(COVER_OUTPUTS)
    state.state = CoverState.CLOSED

    # push status "open"
    inp = ModStatusOutput(address, 0, 100)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_OUTPUTS)
    assert state is not None
    assert state.state == CoverState.OPENING

    # push status "stop"
    inp = ModStatusOutput(address, 0, 0)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_OUTPUTS)
    assert state is not None
    assert state.state not in (CoverState.OPENING, CoverState.CLOSING)

    # push status "close"
    inp = ModStatusOutput(address, 1, 100)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_OUTPUTS)
    assert state is not None
    assert state.state == CoverState.CLOSING


async def test_pushed_relays_status_change(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test the relays cover changes its state on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [False] * 8

    state = hass.states.get(COVER_RELAYS)
    state.state = CoverState.CLOSED

    # push status "open"
    states[0:2] = [True, False]
    inp = ModStatusRelays(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_RELAYS)
    assert state is not None
    assert state.state == CoverState.OPENING

    # push status "stop"
    states[0] = False
    inp = ModStatusRelays(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_RELAYS)
    assert state is not None
    assert state.state not in (CoverState.OPENING, CoverState.CLOSING)

    # push status "close"
    states[0:2] = [True, True]
    inp = ModStatusRelays(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_RELAYS)
    assert state is not None
    assert state.state == CoverState.CLOSING


async def test_unload_config_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the cover is removed when the config entry is unloaded."""
    await init_integration(hass, entry)

    await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(COVER_OUTPUTS).state == STATE_UNAVAILABLE
    assert hass.states.get(COVER_RELAYS).state == STATE_UNAVAILABLE
