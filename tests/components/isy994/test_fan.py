"""Tests for ISY994 fan platform."""

import math
from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_INSTEON
from pyisy.nodes import Node
from pyisy.programs import Program
import pytest

from homeassistant.components.isy994.fan import (
    SPEED_RANGE,
    ISYFanEntity,
    ISYFanProgramEntity,
)
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range


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


def make_fan_entity(node: MagicMock) -> ISYFanEntity:
    """Return an ISYFanEntity with node injected."""
    entity = ISYFanEntity.__new__(ISYFanEntity)
    entity._node = node
    return entity


def make_fan_program_entity(node: MagicMock, actions: MagicMock) -> ISYFanProgramEntity:
    """Return an ISYFanProgramEntity with node/actions injected."""
    entity = ISYFanProgramEntity.__new__(ISYFanProgramEntity)
    entity._node = node
    entity._actions = actions
    return entity


# ---------------------------------------------------------------------------
# ISYFanEntity.percentage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, None, id="unknown"),
        pytest.param(1, ranged_value_to_percentage(SPEED_RANGE, 1), id="min_speed"),
        pytest.param(85, ranged_value_to_percentage(SPEED_RANGE, 85), id="mid_speed"),
        pytest.param(255, ranged_value_to_percentage(SPEED_RANGE, 255), id="max_speed"),
    ],
)
def test_fan_percentage(status: object, expected: int | None) -> None:
    """Percentage maps status through ranged_value_to_percentage."""
    entity = make_fan_entity(make_node(status=status))
    assert entity.percentage == expected


# ---------------------------------------------------------------------------
# ISYFanEntity.speed_count
# ---------------------------------------------------------------------------


def test_fan_speed_count_insteon() -> None:
    """speed_count is 3 for Insteon devices."""
    entity = make_fan_entity(make_node(protocol=PROTO_INSTEON))
    assert entity.speed_count == 3


def test_fan_speed_count_non_insteon() -> None:
    """speed_count is int_states_in_range(SPEED_RANGE) for non-Insteon devices."""
    entity = make_fan_entity(make_node(protocol="zwave"))
    assert entity.speed_count == int_states_in_range(SPEED_RANGE)


# ---------------------------------------------------------------------------
# ISYFanEntity.is_on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, None, id="unknown"),
        pytest.param(0, False, id="off"),
        pytest.param(128, True, id="on"),
        pytest.param(255, True, id="full_speed"),
    ],
)
def test_fan_is_on(status: object, expected: bool | None) -> None:
    """is_on returns None for unknown, False for 0, True otherwise."""
    entity = make_fan_entity(make_node(status=status))
    assert entity.is_on is expected


# ---------------------------------------------------------------------------
# ISYFanEntity.async_set_percentage
# ---------------------------------------------------------------------------


async def test_fan_set_percentage_zero_turns_off() -> None:
    """async_set_percentage(0) calls turn_off."""
    node = make_node()
    node.turn_off = AsyncMock()
    node.turn_on = AsyncMock()
    entity = make_fan_entity(node)
    await entity.async_set_percentage(0)
    node.turn_off.assert_awaited_once()
    node.turn_on.assert_not_awaited()


async def test_fan_set_percentage_nonzero_turns_on() -> None:
    """async_set_percentage with nonzero calls turn_on with correct ISY speed."""
    node = make_node()
    node.turn_on = AsyncMock()
    node.turn_off = AsyncMock()
    entity = make_fan_entity(node)
    percentage = 67
    expected_val = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
    await entity.async_set_percentage(percentage)
    node.turn_on.assert_awaited_once_with(val=expected_val)
    node.turn_off.assert_not_awaited()


# ---------------------------------------------------------------------------
# ISYFanEntity.async_turn_on / async_turn_off
# ---------------------------------------------------------------------------


async def test_fan_turn_on_with_percentage() -> None:
    """async_turn_on forwards the given percentage to async_set_percentage."""
    node = make_node()
    node.turn_on = AsyncMock()
    node.turn_off = AsyncMock()
    entity = make_fan_entity(node)
    await entity.async_turn_on(percentage=50)
    expected_val = math.ceil(percentage_to_ranged_value(SPEED_RANGE, 50))
    node.turn_on.assert_awaited_once_with(val=expected_val)


async def test_fan_turn_on_no_percentage_uses_default() -> None:
    """async_turn_on with no percentage uses 67% default."""
    node = make_node()
    node.turn_on = AsyncMock()
    entity = make_fan_entity(node)
    await entity.async_turn_on()
    expected_val = math.ceil(percentage_to_ranged_value(SPEED_RANGE, 67))
    node.turn_on.assert_awaited_once_with(val=expected_val)


async def test_fan_turn_off() -> None:
    """async_turn_off calls turn_off on the node."""
    node = make_node()
    node.turn_off = AsyncMock()
    entity = make_fan_entity(node)
    await entity.async_turn_off()
    node.turn_off.assert_awaited_once()


# ---------------------------------------------------------------------------
# ISYFanProgramEntity.percentage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, None, id="unknown"),
        pytest.param(85, ranged_value_to_percentage(SPEED_RANGE, 85), id="mid_speed"),
        pytest.param(255, ranged_value_to_percentage(SPEED_RANGE, 255), id="max_speed"),
    ],
)
def test_fan_program_percentage(status: object, expected: int | None) -> None:
    """Percentage maps program status through ranged_value_to_percentage."""
    entity = make_fan_program_entity(make_program(status=status), make_program())
    assert entity.percentage == expected


# ---------------------------------------------------------------------------
# ISYFanProgramEntity.speed_count
# ---------------------------------------------------------------------------


def test_fan_program_speed_count() -> None:
    """speed_count is int_states_in_range(SPEED_RANGE)."""
    entity = make_fan_program_entity(make_program(), make_program())
    assert entity.speed_count == int_states_in_range(SPEED_RANGE)


# ---------------------------------------------------------------------------
# ISYFanProgramEntity.is_on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(0, False, id="off"),
        pytest.param(128, True, id="on"),
    ],
)
def test_fan_program_is_on(status: object, expected: bool) -> None:
    """is_on reflects bool(status != 0) for program entity."""
    entity = make_fan_program_entity(make_program(status=status), make_program())
    assert entity.is_on is expected


# ---------------------------------------------------------------------------
# ISYFanProgramEntity.async_turn_off / async_turn_on
# (Note: turn_off calls run_then; turn_on calls run_else — per source)
# ---------------------------------------------------------------------------


async def test_fan_program_turn_off_success() -> None:
    """async_turn_off calls run_then on the actions program."""
    actions = make_program()
    actions.run_then = AsyncMock(return_value=True)
    entity = make_fan_program_entity(make_program(), actions)
    await entity.async_turn_off()
    actions.run_then.assert_awaited_once()


async def test_fan_program_turn_off_failure_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """async_turn_off logs an error when run_then returns falsy."""
    actions = make_program()
    actions.run_then = AsyncMock(return_value=False)
    entity = make_fan_program_entity(make_program(), actions)
    await entity.async_turn_off()
    assert "Unable to turn off the fan" in caplog.text


async def test_fan_program_turn_on_success() -> None:
    """async_turn_on calls run_else on the actions program."""
    actions = make_program()
    actions.run_else = AsyncMock(return_value=True)
    entity = make_fan_program_entity(make_program(), actions)
    await entity.async_turn_on()
    actions.run_else.assert_awaited_once()


async def test_fan_program_turn_on_failure_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """async_turn_on logs an error when run_else returns falsy."""
    actions = make_program()
    actions.run_else = AsyncMock(return_value=False)
    entity = make_fan_program_entity(make_program(), actions)
    await entity.async_turn_on()
    assert "Unable to turn on the fan" in caplog.text
