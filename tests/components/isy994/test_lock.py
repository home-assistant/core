"""Tests for ISY994 lock platform."""

from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_INSTEON
from pyisy.nodes import Node
from pyisy.programs import Program
import pytest

from homeassistant.components.isy994.lock import ISYLockEntity, ISYLockProgramEntity
from homeassistant.exceptions import HomeAssistantError


def make_node(status: object = 0) -> MagicMock:
    """Return a minimal mock Node."""
    node = MagicMock(spec=Node)
    node.status = status
    node.protocol = PROTO_INSTEON
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


def make_lock_entity(node: MagicMock) -> ISYLockEntity:
    """Return an ISYLockEntity with node injected."""
    entity = ISYLockEntity.__new__(ISYLockEntity)
    entity._node = node
    return entity


def make_lock_program_entity(
    node: MagicMock, actions: MagicMock
) -> ISYLockProgramEntity:
    """Return an ISYLockProgramEntity with node/actions injected."""
    entity = ISYLockProgramEntity.__new__(ISYLockProgramEntity)
    entity._node = node
    entity._actions = actions
    return entity


# ---------------------------------------------------------------------------
# ISYLockEntity.is_locked
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, None, id="unknown"),
        pytest.param(0, False, id="unlocked"),
        pytest.param(100, True, id="locked"),
        pytest.param(50, None, id="undefined_maps_to_none"),
    ],
)
def test_lock_is_locked(status: object, expected: bool | None) -> None:
    """is_locked maps 0→False, 100→True, unknown/other→None."""
    entity = make_lock_entity(make_node(status=status))
    assert entity.is_locked is expected


# ---------------------------------------------------------------------------
# ISYLockEntity actions
# ---------------------------------------------------------------------------


async def test_lock_lock_success() -> None:
    """async_lock calls secure_lock on the node."""
    node = make_node()
    node.secure_lock = AsyncMock(return_value=True)
    entity = make_lock_entity(node)
    await entity.async_lock()
    node.secure_lock.assert_awaited_once()


async def test_lock_lock_failure_raises() -> None:
    """async_lock raises HomeAssistantError when secure_lock returns falsy."""
    node = make_node()
    node.secure_lock = AsyncMock(return_value=False)
    entity = make_lock_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_lock()


async def test_lock_unlock_success() -> None:
    """async_unlock calls secure_unlock on the node."""
    node = make_node()
    node.secure_unlock = AsyncMock(return_value=True)
    entity = make_lock_entity(node)
    await entity.async_unlock()
    node.secure_unlock.assert_awaited_once()


async def test_lock_unlock_failure_raises() -> None:
    """async_unlock raises HomeAssistantError when secure_unlock returns falsy."""
    node = make_node()
    node.secure_unlock = AsyncMock(return_value=False)
    entity = make_lock_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_unlock()


async def test_lock_set_user_code_success() -> None:
    """async_set_zwave_lock_user_code calls set_zwave_lock_code on the node."""
    node = make_node()
    node.set_zwave_lock_code = AsyncMock(return_value=True)
    entity = make_lock_entity(node)
    await entity.async_set_zwave_lock_user_code(user_num=1, code=1234)
    node.set_zwave_lock_code.assert_awaited_once_with(1, 1234)


async def test_lock_set_user_code_failure_raises() -> None:
    """async_set_zwave_lock_user_code raises on failure."""
    node = make_node()
    node.set_zwave_lock_code = AsyncMock(return_value=False)
    entity = make_lock_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_set_zwave_lock_user_code(user_num=1, code=1234)


async def test_lock_delete_user_code_success() -> None:
    """async_delete_zwave_lock_user_code calls delete_zwave_lock_code on the node."""
    node = make_node()
    node.delete_zwave_lock_code = AsyncMock(return_value=True)
    entity = make_lock_entity(node)
    await entity.async_delete_zwave_lock_user_code(user_num=1)
    node.delete_zwave_lock_code.assert_awaited_once_with(1)


async def test_lock_delete_user_code_failure_raises() -> None:
    """async_delete_zwave_lock_user_code raises on failure."""
    node = make_node()
    node.delete_zwave_lock_code = AsyncMock(return_value=False)
    entity = make_lock_entity(node)
    with pytest.raises(HomeAssistantError):
        await entity.async_delete_zwave_lock_user_code(user_num=1)


# ---------------------------------------------------------------------------
# ISYLockProgramEntity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(1, True, id="locked"),
        pytest.param(0, False, id="unlocked"),
    ],
)
def test_lock_program_is_locked(status: object, expected: bool) -> None:
    """is_locked reflects the program status."""
    entity = make_lock_program_entity(make_program(status=status), make_program())
    assert entity.is_locked is expected


async def test_lock_program_lock_success() -> None:
    """async_lock calls run_then on the actions program."""
    actions = make_program()
    actions.run_then = AsyncMock(return_value=True)
    entity = make_lock_program_entity(make_program(), actions)
    await entity.async_lock()
    actions.run_then.assert_awaited_once()


async def test_lock_program_lock_failure_raises() -> None:
    """async_lock raises when run_then returns falsy."""
    actions = make_program()
    actions.run_then = AsyncMock(return_value=False)
    entity = make_lock_program_entity(make_program(), actions)
    with pytest.raises(HomeAssistantError):
        await entity.async_lock()


async def test_lock_program_unlock_success() -> None:
    """async_unlock calls run_else on the actions program."""
    actions = make_program()
    actions.run_else = AsyncMock(return_value=True)
    entity = make_lock_program_entity(make_program(), actions)
    await entity.async_unlock()
    actions.run_else.assert_awaited_once()


async def test_lock_program_unlock_failure_raises() -> None:
    """async_unlock raises when run_else returns falsy."""
    actions = make_program()
    actions.run_else = AsyncMock(return_value=False)
    entity = make_lock_program_entity(make_program(), actions)
    with pytest.raises(HomeAssistantError):
        await entity.async_unlock()
