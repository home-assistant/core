"""Tests for ISY994 cover platform."""

from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_INSTEON
from pyisy.nodes import Node
from pyisy.programs import Program
import pytest

from homeassistant.components.isy994.const import UOM_8_BIT_RANGE
from homeassistant.components.isy994.cover import ISYCoverEntity, ISYCoverProgramEntity


def make_node(status: object = 0, uom: str = "100") -> MagicMock:
    """Return a minimal mock Node."""
    node = MagicMock(spec=Node)
    node.status = status
    node.uom = uom
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


def make_cover_entity(node: MagicMock) -> ISYCoverEntity:
    """Return an ISYCoverEntity with node injected."""
    entity = ISYCoverEntity.__new__(ISYCoverEntity)
    entity._node = node
    return entity


def make_cover_program_entity(
    node: MagicMock, actions: MagicMock
) -> ISYCoverProgramEntity:
    """Return an ISYCoverProgramEntity with node/actions injected."""
    entity = ISYCoverProgramEntity.__new__(ISYCoverProgramEntity)
    entity._node = node
    entity._actions = actions
    return entity


# ---------------------------------------------------------------------------
# ISYCoverEntity.current_cover_position
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "uom", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, "100", None, id="unknown"),
        pytest.param(128, UOM_8_BIT_RANGE, 50, id="8bit_mid"),
        pytest.param(0, UOM_8_BIT_RANGE, 0, id="8bit_zero"),
        pytest.param(255, UOM_8_BIT_RANGE, 100, id="8bit_full"),
        pytest.param(50, "0", 50, id="percent_direct"),
        pytest.param(0, "0", 0, id="percent_zero"),
        pytest.param(100, "0", 100, id="percent_full"),
        pytest.param(150, "0", 100, id="percent_clamp_high"),
        pytest.param(-10, "0", 0, id="percent_clamp_low"),
    ],
)
def test_cover_current_position(status: object, uom: str, expected: int | None) -> None:
    """current_cover_position scales correctly for 8-bit and percent UOMs."""
    node = make_node(status=status, uom=uom)
    entity = make_cover_entity(node)
    result = entity.current_cover_position
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, abs=1)


# ---------------------------------------------------------------------------
# ISYCoverEntity.is_closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, None, id="unknown"),
        pytest.param(0, True, id="closed"),
        pytest.param(50, False, id="open"),
    ],
)
def test_cover_is_closed(status: object, expected: bool | None) -> None:
    """is_closed returns True when status==0, False otherwise, None when unknown."""
    entity = make_cover_entity(make_node(status=status))
    assert entity.is_closed is expected


# ---------------------------------------------------------------------------
# ISYCoverEntity actions
# ---------------------------------------------------------------------------


async def test_cover_open_success() -> None:
    """async_open_cover calls node.turn_on()."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=True)
    entity = make_cover_entity(node)
    await entity.async_open_cover()
    node.turn_on.assert_awaited_once()


async def test_cover_close_success() -> None:
    """async_close_cover calls node.turn_off()."""
    node = make_node()
    node.turn_off = AsyncMock(return_value=True)
    entity = make_cover_entity(node)
    await entity.async_close_cover()
    node.turn_off.assert_awaited_once()


async def test_cover_set_position_percent() -> None:
    """async_set_cover_position passes position directly for percent UOM."""
    node = make_node(uom="0")
    node.turn_on = AsyncMock(return_value=True)
    entity = make_cover_entity(node)
    await entity.async_set_cover_position(position=75)
    node.turn_on.assert_awaited_once_with(val=75)


async def test_cover_set_position_8bit_scaled() -> None:
    """async_set_cover_position scales position for 8-bit UOM."""
    node = make_node(uom=UOM_8_BIT_RANGE)
    node.turn_on = AsyncMock(return_value=True)
    entity = make_cover_entity(node)
    await entity.async_set_cover_position(position=100)
    node.turn_on.assert_awaited_once_with(val=255)


# ---------------------------------------------------------------------------
# ISYCoverProgramEntity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(1, True, id="closed"),
        pytest.param(0, False, id="open"),
    ],
)
def test_cover_program_is_closed(status: object, expected: bool) -> None:
    """is_closed reflects the program status (non-zero = closed)."""
    entity = make_cover_program_entity(make_program(status=status), make_program())
    assert entity.is_closed is expected


async def test_cover_program_open() -> None:
    """async_open_cover calls run_then on the actions program."""
    actions = make_program()
    actions.run_then = AsyncMock(return_value=True)
    entity = make_cover_program_entity(make_program(), actions)
    await entity.async_open_cover()
    actions.run_then.assert_awaited_once()


async def test_cover_program_close() -> None:
    """async_close_cover calls run_else on the actions program."""
    actions = make_program()
    actions.run_else = AsyncMock(return_value=True)
    entity = make_cover_program_entity(make_program(), actions)
    await entity.async_close_cover()
    actions.run_else.assert_awaited_once()
