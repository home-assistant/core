"""Tests for ISY994 switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_GROUP, PROTO_INSTEON
from pyisy.nodes import Node
from pyisy.programs import Program
import pytest

from homeassistant.components.isy994.switch import (
    ISYEnableSwitchEntity,
    ISYSwitchEntity,
    ISYSwitchEntityDescription,
    ISYSwitchProgramEntity,
)
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_node(status: object = 0, protocol: str = PROTO_INSTEON) -> MagicMock:
    """Return a minimal mock Node."""
    node = MagicMock(spec=Node)
    node.status = status
    node.protocol = protocol
    node.address = "1 1"
    node.status_events = MagicMock()
    node.status_events.subscribe.return_value = MagicMock()
    node.control_events = MagicMock()
    node.control_events.subscribe.return_value = MagicMock()
    return node


def make_program(status: object = 0) -> MagicMock:
    """Return a minimal mock Program."""
    prog = MagicMock(spec=Program)
    prog.status = status
    prog.address = "0001"
    prog.status_events = MagicMock()
    prog.status_events.subscribe.return_value = MagicMock()
    return prog


def make_switch_entity(node: MagicMock) -> ISYSwitchEntity:
    """Return an ISYSwitchEntity with node injected."""
    with patch.object(ISYSwitchEntity, "async_added_to_hass"):
        entity = ISYSwitchEntity.__new__(ISYSwitchEntity)
        entity._node = node
    return entity


def make_switch_program_entity(
    node: MagicMock, actions: MagicMock
) -> ISYSwitchProgramEntity:
    """Return an ISYSwitchProgramEntity with node/actions injected."""
    entity = ISYSwitchProgramEntity.__new__(ISYSwitchProgramEntity)
    entity._node = node
    entity._actions = actions
    return entity


# ---------------------------------------------------------------------------
# ISYSwitchEntity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(1, True, id="on"),
        pytest.param(0, False, id="off"),
        pytest.param(ISY_VALUE_UNKNOWN, None, id="unknown"),
    ],
)
def test_switch_is_on(status: object, expected: bool | None) -> None:
    """is_on returns True, False, or None based on node.status."""
    entity = make_switch_entity(make_node(status=status))
    assert entity.is_on is expected


async def test_switch_turn_on_success() -> None:
    """async_turn_on succeeds when node.turn_on returns truthy."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=True)
    entity = make_switch_entity(node)
    await entity.async_turn_on()
    node.turn_on.assert_awaited_once()


async def test_switch_turn_on_failure_raises() -> None:
    """async_turn_on raises HomeAssistantError when node.turn_on returns falsy."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=False)
    entity = make_switch_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()


async def test_switch_turn_off_success() -> None:
    """async_turn_off succeeds when node.turn_off returns truthy."""
    node = make_node()
    node.turn_off = AsyncMock(return_value=True)
    entity = make_switch_entity(node)
    await entity.async_turn_off()
    node.turn_off.assert_awaited_once()


async def test_switch_turn_off_failure_raises() -> None:
    """async_turn_off raises HomeAssistantError when node.turn_off returns falsy."""
    node = make_node()
    node.turn_off = AsyncMock(return_value=False)
    entity = make_switch_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()


@pytest.mark.parametrize(
    ("protocol", "expected_icon"),
    [
        pytest.param(PROTO_GROUP, "mdi:google-circles-communities", id="group"),
        pytest.param(PROTO_INSTEON, None, id="insteon"),
    ],
)
def test_switch_icon(protocol: str, expected_icon: str | None) -> None:
    """Icon returns group icon for PROTO_GROUP nodes, None otherwise."""
    entity = make_switch_entity(make_node(protocol=protocol))
    assert entity.icon == expected_icon


# ---------------------------------------------------------------------------
# ISYSwitchProgramEntity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(1, True, id="on"),
        pytest.param(0, False, id="off"),
    ],
)
def test_switch_program_is_on(status: object, expected: bool) -> None:
    """is_on reflects the program node status."""
    entity = make_switch_program_entity(make_program(status=status), make_program())
    assert entity.is_on is expected


async def test_switch_program_turn_on_success() -> None:
    """async_turn_on calls run_then on the actions program."""
    actions = make_program()
    actions.run_then = AsyncMock(return_value=True)
    entity = make_switch_program_entity(make_program(), actions)
    await entity.async_turn_on()
    actions.run_then.assert_awaited_once()


async def test_switch_program_turn_on_failure_raises() -> None:
    """async_turn_on raises when run_then returns falsy."""
    actions = make_program()
    actions.run_then = AsyncMock(return_value=False)
    entity = make_switch_program_entity(make_program(), actions)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()


async def test_switch_program_turn_off_success() -> None:
    """async_turn_off calls run_else on the actions program."""
    actions = make_program()
    actions.run_else = AsyncMock(return_value=True)
    entity = make_switch_program_entity(make_program(), actions)
    await entity.async_turn_off()
    actions.run_else.assert_awaited_once()


async def test_switch_program_turn_off_failure_raises() -> None:
    """async_turn_off raises when run_else returns falsy."""
    actions = make_program()
    actions.run_else = AsyncMock(return_value=False)
    entity = make_switch_program_entity(make_program(), actions)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()


# ---------------------------------------------------------------------------
# ISYEnableSwitchEntity
# ---------------------------------------------------------------------------


def make_enable_switch_entity(node: MagicMock) -> ISYEnableSwitchEntity:
    """Return an ISYEnableSwitchEntity with node injected."""
    entity = ISYEnableSwitchEntity.__new__(ISYEnableSwitchEntity)
    entity._node = node
    entity._control = "enabled"
    entity._attr_unique_id = "test-uuid_1 1_enabled"
    entity._attr_name = "Enabled"
    entity.entity_description = ISYSwitchEntityDescription(
        key="enabled",
        device_class=SwitchDeviceClass.SWITCH,
        name="Enabled",
        entity_category=EntityCategory.CONFIG,
    )
    entity._change_handler = None
    return entity


def test_enable_switch_is_on_true() -> None:
    """is_on returns True when node.enabled is truthy."""
    node = make_node()
    node.enabled = True
    entity = make_enable_switch_entity(node)
    assert entity.is_on is True


def test_enable_switch_is_on_false() -> None:
    """is_on returns False when node.enabled is falsy."""
    node = make_node()
    node.enabled = False
    entity = make_enable_switch_entity(node)
    assert entity.is_on is False


def test_enable_switch_always_available() -> None:
    """Available always returns True."""
    entity = make_enable_switch_entity(make_node())
    assert entity.available is True


async def test_enable_switch_turn_on_success() -> None:
    """async_turn_on calls node.enable()."""
    node = make_node()
    node.enable = AsyncMock(return_value=True)
    entity = make_enable_switch_entity(node)
    await entity.async_turn_on()
    node.enable.assert_awaited_once()


async def test_enable_switch_turn_on_failure_raises() -> None:
    """async_turn_on raises HomeAssistantError when node.enable fails."""
    node = make_node()
    node.enable = AsyncMock(return_value=False)
    entity = make_enable_switch_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()


async def test_enable_switch_turn_off_success() -> None:
    """async_turn_off calls node.disable()."""
    node = make_node()
    node.disable = AsyncMock(return_value=True)
    entity = make_enable_switch_entity(node)
    await entity.async_turn_off()
    node.disable.assert_awaited_once()


async def test_enable_switch_turn_off_failure_raises() -> None:
    """async_turn_off raises HomeAssistantError when node.disable fails."""
    node = make_node()
    node.disable = AsyncMock(return_value=False)
    entity = make_enable_switch_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()
