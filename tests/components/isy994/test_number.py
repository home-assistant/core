"""Tests for ISY994 number platform."""

from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import (
    CMD_BACKLIGHT,
    ISY_VALUE_UNKNOWN,
    PROP_ON_LEVEL,
    UOM_PERCENTAGE,
)
from pyisy.nodes import Node
from pyisy.variables import Variable
import pytest

from homeassistant.components.isy994.const import UOM_8_BIT_RANGE
from homeassistant.components.isy994.number import (
    BACKLIGHT_MEMORY_FILTER,
    CONTROL_DESC,
    ON_RANGE,
    ISYAuxControlNumberEntity,
    ISYBacklightNumberEntity,
    ISYVariableNumberEntity,
)
from homeassistant.components.number import NumberEntityDescription
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)


def make_device_info() -> DeviceInfo:
    """Return a minimal DeviceInfo."""
    return DeviceInfo(identifiers={("isy994", "test-device")})


def _make_prop(value: object, uom: str = "") -> MagicMock:
    """Return a mock NodeProperty."""
    prop = MagicMock()
    prop.value = value
    prop.uom = uom
    return prop


def make_aux_number_entity(
    control: str = PROP_ON_LEVEL,
    prop_value: object = 128,
    prop_uom: str = UOM_8_BIT_RANGE,
    description: NumberEntityDescription | None = None,
) -> ISYAuxControlNumberEntity:
    """Return an ISYAuxControlNumberEntity with injected attributes."""
    if description is None:
        description = CONTROL_DESC[PROP_ON_LEVEL]
    node = MagicMock(spec=Node)
    node.address = "1 1"
    node.primary_node = "1 1"
    node.aux_properties = {control: _make_prop(prop_value, uom=prop_uom)}
    entity = ISYAuxControlNumberEntity.__new__(ISYAuxControlNumberEntity)
    entity._node = node
    entity._control = control
    entity.entity_description = description
    return entity


def make_variable_entity(
    status: object = 42,
    init: object = 10,
    prec: int = 0,
    init_entity: bool = False,
) -> ISYVariableNumberEntity:
    """Return an ISYVariableNumberEntity."""
    node = MagicMock(spec=Variable)
    node.status = status
    node.init = init
    node.prec = prec
    node.last_edited = "2024-01-01"
    node.address = "1"
    node.status_events = MagicMock()
    description = NumberEntityDescription(
        key="1",
        name="Test Variable",
        native_step=1.0,
        native_min_value=-100.0,
        native_max_value=100.0,
    )
    return ISYVariableNumberEntity(
        node=node,
        unique_id="uid_var",
        description=description,
        device_info=make_device_info(),
        init_entity=init_entity,
    )


def make_backlight_entity(
    native_value: float = 0,
) -> ISYBacklightNumberEntity:
    """Return an ISYBacklightNumberEntity with injected attributes."""
    node = MagicMock(spec=Node)
    node.address = "1 1"
    node.primary_node = "1 1"
    node.send_cmd = AsyncMock(return_value=True)
    entity = ISYBacklightNumberEntity.__new__(ISYBacklightNumberEntity)
    entity._node = node
    entity._control = CMD_BACKLIGHT
    entity.entity_description = CONTROL_DESC[CMD_BACKLIGHT]
    entity._attr_native_value = native_value
    entity.async_write_ha_state = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# ISYAuxControlNumberEntity.native_value
# ---------------------------------------------------------------------------


def test_aux_number_native_value_unknown() -> None:
    """native_value is None when the aux property value is unknown."""
    entity = make_aux_number_entity(prop_value=ISY_VALUE_UNKNOWN)
    assert entity.native_value is None


def test_aux_number_native_value_percentage_8bit() -> None:
    """native_value scales 0-255 to percentage for PERCENTAGE+UOM_8_BIT_RANGE."""
    entity = make_aux_number_entity(prop_value=128, prop_uom=UOM_8_BIT_RANGE)
    expected = ranged_value_to_percentage(ON_RANGE, 128)
    assert entity.native_value == expected


def test_aux_number_native_value_percentage_non_8bit() -> None:
    """native_value returns int(value) for PERCENTAGE without UOM_8_BIT_RANGE."""
    entity = make_aux_number_entity(prop_value=75, prop_uom="")
    assert entity.native_value == 75


def test_aux_number_native_value_non_percentage() -> None:
    """native_value returns int(value) for non-percentage descriptions."""
    desc = NumberEntityDescription(key="test", native_min_value=0, native_max_value=100)
    entity = make_aux_number_entity(
        control="TEST",
        prop_value=42,
        prop_uom="",
        description=desc,
    )
    entity._node.aux_properties = {"TEST": _make_prop(42, uom="")}
    assert entity.native_value == 42


# ---------------------------------------------------------------------------
# ISYAuxControlNumberEntity.async_set_native_value
# ---------------------------------------------------------------------------


async def test_aux_number_set_value_on_level_8bit() -> None:
    """async_set_native_value calls set_on_level with scaled value for PROP_ON_LEVEL + 8-bit UOM."""
    entity = make_aux_number_entity(
        control=PROP_ON_LEVEL, prop_value=50, prop_uom=UOM_8_BIT_RANGE
    )
    entity._node.set_on_level = AsyncMock()
    await entity.async_set_native_value(50.0)
    expected = percentage_to_ranged_value(ON_RANGE, 50)
    entity._node.set_on_level.assert_awaited_once_with(expected)


async def test_aux_number_set_value_on_level_direct() -> None:
    """async_set_native_value calls set_on_level directly for non-8-bit UOM."""
    entity = make_aux_number_entity(control=PROP_ON_LEVEL, prop_value=50, prop_uom="")
    entity._node.set_on_level = AsyncMock()
    await entity.async_set_native_value(75.0)
    entity._node.set_on_level.assert_awaited_once_with(75.0)


async def test_aux_number_set_value_send_cmd_success() -> None:
    """async_set_native_value calls send_cmd for non-PROP_ON_LEVEL controls."""
    desc = NumberEntityDescription(
        key=CMD_BACKLIGHT,
        native_min_value=0,
        native_max_value=100,
    )
    entity = make_aux_number_entity(
        control=CMD_BACKLIGHT, prop_value=50, prop_uom="", description=desc
    )
    entity._node.aux_properties = {CMD_BACKLIGHT: _make_prop(50, uom="")}
    entity._node.send_cmd = AsyncMock(return_value=True)
    await entity.async_set_native_value(30.0)
    entity._node.send_cmd.assert_awaited_once_with(CMD_BACKLIGHT, val=30.0, uom="")


async def test_aux_number_set_value_send_cmd_failure_raises() -> None:
    """async_set_native_value raises HomeAssistantError when send_cmd returns falsy."""
    desc = NumberEntityDescription(
        key=CMD_BACKLIGHT,
        native_min_value=0,
        native_max_value=100,
    )
    entity = make_aux_number_entity(
        control=CMD_BACKLIGHT, prop_value=50, prop_uom="", description=desc
    )
    entity._node.aux_properties = {CMD_BACKLIGHT: _make_prop(50, uom="")}
    entity._node.send_cmd = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(30.0)


# ---------------------------------------------------------------------------
# ISYVariableNumberEntity.native_value
# ---------------------------------------------------------------------------


def test_variable_native_value_current() -> None:
    """native_value uses node.status when init_entity is False."""
    entity = make_variable_entity(status=42, init=10, init_entity=False)
    assert entity.native_value == 42.0


def test_variable_native_value_init() -> None:
    """native_value uses node.init when init_entity is True."""
    entity = make_variable_entity(status=42, init=10, init_entity=True)
    assert entity.native_value == 10.0


# ---------------------------------------------------------------------------
# ISYVariableNumberEntity.extra_state_attributes
# ---------------------------------------------------------------------------


def test_variable_extra_state_attributes() -> None:
    """extra_state_attributes returns last_edited from the node."""
    entity = make_variable_entity()
    assert entity.extra_state_attributes == {"last_edited": "2024-01-01"}


# ---------------------------------------------------------------------------
# ISYVariableNumberEntity.async_set_native_value
# ---------------------------------------------------------------------------


async def test_variable_set_value_success() -> None:
    """async_set_native_value calls node.set_value and does not raise on success."""
    entity = make_variable_entity()
    entity._node.set_value = AsyncMock(return_value=True)
    await entity.async_set_native_value(99.0)
    entity._node.set_value.assert_awaited_once_with(99.0, init=False)


async def test_variable_set_value_init_success() -> None:
    """async_set_native_value calls node.set_value with init=True for init entities."""
    entity = make_variable_entity(init_entity=True)
    entity._node.set_value = AsyncMock(return_value=True)
    await entity.async_set_native_value(5.0)
    entity._node.set_value.assert_awaited_once_with(5.0, init=True)


async def test_variable_set_value_failure_raises() -> None:
    """async_set_native_value raises HomeAssistantError when set_value returns falsy."""
    entity = make_variable_entity()
    entity._node.set_value = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(99.0)


# ---------------------------------------------------------------------------
# ISYBacklightNumberEntity.async_on_memory_write
# ---------------------------------------------------------------------------


def test_backlight_memory_write_filter_mismatch_ignored() -> None:
    """async_on_memory_write ignores events that don't match the backlight filter."""
    entity = make_backlight_entity(native_value=50)
    event = MagicMock()
    event.event_info = {"memory": "OTHER_ADDR", "cmd1": "OTHER_CMD", "value": 64}
    entity.async_on_memory_write(event, key="test")
    assert entity._attr_native_value == 50
    entity.async_write_ha_state.assert_not_called()


def test_backlight_memory_write_same_value_ignored() -> None:
    """async_on_memory_write skips update when computed value equals current."""
    entity = make_backlight_entity(native_value=50)
    raw = 64  # ranged_value_to_percentage((0, 127), 64) == 50
    event = MagicMock()
    event.event_info = {**BACKLIGHT_MEMORY_FILTER, "value": raw}
    same_value = ranged_value_to_percentage((0, 127), raw)
    entity._attr_native_value = same_value
    entity.async_on_memory_write(event, key="test")
    entity.async_write_ha_state.assert_not_called()


def test_backlight_memory_write_updates_value() -> None:
    """async_on_memory_write updates native_value and calls async_write_ha_state."""
    entity = make_backlight_entity(native_value=0)
    raw = 64
    event = MagicMock()
    event.event_info = {**BACKLIGHT_MEMORY_FILTER, "value": raw}
    entity.async_on_memory_write(event, key="test")
    expected = ranged_value_to_percentage((0, 127), raw)
    assert entity._attr_native_value == expected
    entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# ISYBacklightNumberEntity.async_set_native_value
# ---------------------------------------------------------------------------


async def test_backlight_set_value_success() -> None:
    """async_set_native_value calls send_cmd and updates native_value on success."""
    entity = make_backlight_entity()
    entity._node.send_cmd = AsyncMock(return_value=True)
    await entity.async_set_native_value(75.0)
    entity._node.send_cmd.assert_awaited_once_with(
        CMD_BACKLIGHT, val=75, uom=UOM_PERCENTAGE
    )
    assert entity._attr_native_value == 75.0
    entity.async_write_ha_state.assert_called_once()


async def test_backlight_set_value_failure_raises() -> None:
    """async_set_native_value raises HomeAssistantError when send_cmd returns falsy."""
    entity = make_backlight_entity()
    entity._node.send_cmd = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(75.0)
