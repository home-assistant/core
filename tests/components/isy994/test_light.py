"""Tests for ISY994 light platform."""

from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import ISY_VALUE_UNKNOWN
from pyisy.helpers import NodeProperty
from pyisy.nodes import Node
import pytest

from homeassistant.components.isy994.const import UOM_PERCENTAGE
from homeassistant.components.isy994.light import ATTR_LAST_BRIGHTNESS, ISYLightEntity


def make_node(status: object = 0, uom: str = "") -> MagicMock:
    """Return a minimal mock Node."""
    node = MagicMock(spec=Node)
    node.status = status
    node.uom = uom
    node.protocol = "insteon"
    node.address = "1 1"
    node.status_events = MagicMock()
    node.status_events.subscribe.return_value = MagicMock()
    node.control_events = MagicMock()
    node.control_events.subscribe.return_value = MagicMock()
    return node


def make_light_entity(node: MagicMock, restore: bool = False) -> ISYLightEntity:
    """Return an ISYLightEntity with node injected."""
    entity = ISYLightEntity.__new__(ISYLightEntity)
    entity._node = node
    entity._last_brightness = None
    entity._restore_light_state = restore
    entity._attrs = {}
    entity.async_write_ha_state = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# ISYLightEntity.is_on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, False, id="unknown_is_off"),
        pytest.param(0, False, id="off"),
        pytest.param(128, True, id="on"),
        pytest.param(255, True, id="full_brightness"),
    ],
)
def test_light_is_on(status: object, expected: bool) -> None:
    """is_on returns False for unknown or 0, True for nonzero."""
    entity = make_light_entity(make_node(status=status))
    assert entity.is_on is expected


# ---------------------------------------------------------------------------
# ISYLightEntity.brightness
# ---------------------------------------------------------------------------


def test_light_brightness_unknown() -> None:
    """Brightness returns None when status is unknown."""
    entity = make_light_entity(make_node(status=ISY_VALUE_UNKNOWN))
    assert entity.brightness is None


def test_light_brightness_raw() -> None:
    """Brightness returns raw status for non-percentage UOM."""
    entity = make_light_entity(make_node(status=200))
    assert entity.brightness == 200


def test_light_brightness_percentage_uom() -> None:
    """Brightness scales status from 0-100 to 0-255 for percentage UOM."""
    entity = make_light_entity(make_node(status=50, uom=UOM_PERCENTAGE))
    assert entity.brightness == round(50 * 255.0 / 100.0)


# ---------------------------------------------------------------------------
# ISYLightEntity.async_turn_off
# ---------------------------------------------------------------------------


async def test_light_turn_off_success() -> None:
    """async_turn_off calls turn_off and saves last brightness."""
    node = make_node(status=200)
    node.turn_off = AsyncMock(return_value=True)
    entity = make_light_entity(node)
    await entity.async_turn_off()
    node.turn_off.assert_awaited_once()
    assert entity._last_brightness == 200


async def test_light_turn_off_failure_logs(caplog: pytest.LogCaptureFixture) -> None:
    """async_turn_off logs debug when turn_off returns falsy."""
    node = make_node(status=200)
    node.turn_off = AsyncMock(return_value=False)
    entity = make_light_entity(node)
    await entity.async_turn_off()
    assert "Unable to turn off light" in caplog.text


# ---------------------------------------------------------------------------
# ISYLightEntity.async_turn_on
# ---------------------------------------------------------------------------


async def test_light_turn_on_explicit_brightness() -> None:
    """async_turn_on passes explicit brightness to node.turn_on."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=True)
    entity = make_light_entity(node)
    await entity.async_turn_on(brightness=128)
    node.turn_on.assert_awaited_once_with(val=128)


async def test_light_turn_on_no_brightness() -> None:
    """async_turn_on with no brightness calls turn_on(val=None)."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=True)
    entity = make_light_entity(node)
    await entity.async_turn_on()
    node.turn_on.assert_awaited_once_with(val=None)


async def test_light_turn_on_restore_uses_last_brightness() -> None:
    """async_turn_on uses last_brightness when restore is enabled and no brightness given."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=True)
    entity = make_light_entity(node, restore=True)
    entity._last_brightness = 180
    await entity.async_turn_on()
    node.turn_on.assert_awaited_once_with(val=180)


async def test_light_turn_on_restore_no_last_brightness() -> None:
    """async_turn_on with restore enabled but no last_brightness calls turn_on(val=None)."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=True)
    entity = make_light_entity(node, restore=True)
    entity._last_brightness = None
    await entity.async_turn_on()
    node.turn_on.assert_awaited_once_with(val=None)


async def test_light_turn_on_percentage_uom_scales_brightness() -> None:
    """async_turn_on scales brightness to 0-100 range for percentage UOM."""
    node = make_node(uom=UOM_PERCENTAGE)
    node.turn_on = AsyncMock(return_value=True)
    entity = make_light_entity(node)
    await entity.async_turn_on(brightness=255)
    node.turn_on.assert_awaited_once_with(val=100)


async def test_light_turn_on_failure_logs(caplog: pytest.LogCaptureFixture) -> None:
    """async_turn_on logs debug when turn_on returns falsy."""
    node = make_node()
    node.turn_on = AsyncMock(return_value=False)
    entity = make_light_entity(node)
    await entity.async_turn_on(brightness=128)
    assert "Unable to turn on light" in caplog.text


# ---------------------------------------------------------------------------
# ISYLightEntity.async_on_update
# ---------------------------------------------------------------------------


def test_light_on_update_nonzero_saves_brightness() -> None:
    """async_on_update saves last_brightness when status is nonzero."""
    node = make_node(status=200)
    entity = make_light_entity(node)
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event)
    assert entity._last_brightness == 200


def test_light_on_update_percentage_uom_saves_scaled_brightness() -> None:
    """async_on_update saves scaled last_brightness for percentage UOM."""
    node = make_node(status=50, uom=UOM_PERCENTAGE)
    entity = make_light_entity(node)
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event)
    assert entity._last_brightness == round(50 * 255.0 / 100.0)


def test_light_on_update_zero_does_not_save_brightness() -> None:
    """async_on_update does not update last_brightness when status is 0."""
    node = make_node(status=0)
    entity = make_light_entity(node)
    entity._last_brightness = 150
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event)
    assert entity._last_brightness == 150


def test_light_on_update_unknown_does_not_save_brightness() -> None:
    """async_on_update does not update last_brightness when status is unknown."""
    node = make_node(status=ISY_VALUE_UNKNOWN)
    entity = make_light_entity(node)
    entity._last_brightness = 150
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event)
    assert entity._last_brightness == 150


# ---------------------------------------------------------------------------
# ISYLightEntity.extra_state_attributes
# ---------------------------------------------------------------------------


def test_light_extra_state_attributes_includes_last_brightness() -> None:
    """extra_state_attributes includes ATTR_LAST_BRIGHTNESS."""
    entity = make_light_entity(make_node())
    entity._last_brightness = 180
    attribs = entity.extra_state_attributes
    assert attribs[ATTR_LAST_BRIGHTNESS] == 180
