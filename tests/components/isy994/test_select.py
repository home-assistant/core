"""Tests for ISY994 select platform."""

from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import (
    BACKLIGHT_INDEX,
    CMD_BACKLIGHT,
    ISY_VALUE_UNKNOWN,
    PROP_RAMP_RATE,
    UOM_INDEX as ISY_UOM_INDEX,
    UOM_TO_STATES,
)
from pyisy.nodes import Node
import pytest

from homeassistant.components.isy994.select import (
    BACKLIGHT_MEMORY_FILTER,
    RAMP_RATE_OPTIONS,
    ISYAuxControlIndexSelectEntity,
    ISYBacklightSelectEntity,
    ISYRampRateSelectEntity,
    time_string,
)
from homeassistant.components.select import SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo


def make_device_info() -> DeviceInfo:
    """Return a minimal DeviceInfo."""
    return DeviceInfo(identifiers={("isy994", "test-device")})


def _make_prop(value: object, uom: str = "", formatted: str = "") -> MagicMock:
    """Return a mock NodeProperty."""
    prop = MagicMock()
    prop.value = value
    prop.uom = uom
    prop.formatted = formatted
    return prop


def _make_select_description(
    options: list[str] | None = None,
) -> SelectEntityDescription:
    """Return a minimal SelectEntityDescription."""
    return SelectEntityDescription(
        key="test",
        entity_category=EntityCategory.CONFIG,
        options=options or [],
    )


def make_ramp_rate_entity(prop_value: object = 0) -> ISYRampRateSelectEntity:
    """Return an ISYRampRateSelectEntity with injected attributes."""
    node = MagicMock(spec=Node)
    node.address = "1 1"
    node.primary_node = "1 1"
    node.aux_properties = {PROP_RAMP_RATE: _make_prop(prop_value)}
    entity = ISYRampRateSelectEntity.__new__(ISYRampRateSelectEntity)
    entity._node = node
    entity._control = PROP_RAMP_RATE
    entity.entity_description = _make_select_description(RAMP_RATE_OPTIONS)
    return entity


def make_index_select_entity(
    control: str = "TEST_CTRL",
    prop_value: object = 0,
    prop_uom: str = "",
    prop_formatted: str = "formatted_value",
    options: list[str] | None = None,
) -> ISYAuxControlIndexSelectEntity:
    """Return an ISYAuxControlIndexSelectEntity with injected attributes."""
    node = MagicMock(spec=Node)
    node.address = "1 1"
    node.primary_node = "1 1"
    node.aux_properties = {
        control: _make_prop(prop_value, uom=prop_uom, formatted=prop_formatted)
    }
    entity = ISYAuxControlIndexSelectEntity.__new__(ISYAuxControlIndexSelectEntity)
    entity._node = node
    entity._control = control
    entity.entity_description = _make_select_description(options or [])
    return entity


def make_backlight_select_entity(
    current_option: str | None = None,
) -> ISYBacklightSelectEntity:
    """Return an ISYBacklightSelectEntity with injected attributes."""
    node = MagicMock(spec=Node)
    node.address = "1 1"
    node.primary_node = "1 1"
    node.send_cmd = AsyncMock(return_value=True)
    entity = ISYBacklightSelectEntity.__new__(ISYBacklightSelectEntity)
    entity._node = node
    entity._control = CMD_BACKLIGHT
    entity.entity_description = _make_select_description(BACKLIGHT_INDEX)
    entity._attr_current_option = current_option
    entity.async_write_ha_state = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# time_string
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        pytest.param(0, f"0 {UnitOfTime.SECONDS}", id="zero"),
        pytest.param(30, f"30 {UnitOfTime.SECONDS}", id="under_60"),
        pytest.param(59, f"59 {UnitOfTime.SECONDS}", id="just_under_60"),
        pytest.param(60, f"1.0 {UnitOfTime.MINUTES}", id="exactly_60"),
        pytest.param(90, f"1.5 {UnitOfTime.MINUTES}", id="ninety_seconds"),
        pytest.param(480, f"8.0 {UnitOfTime.MINUTES}", id="eight_minutes"),
    ],
)
def test_time_string(seconds: int, expected: str) -> None:
    """time_string formats seconds and minutes correctly."""
    assert time_string(seconds) == expected


# ---------------------------------------------------------------------------
# ISYRampRateSelectEntity.current_option
# ---------------------------------------------------------------------------


def test_ramp_rate_current_option_unknown() -> None:
    """current_option is None when the ramp rate property value is unknown."""
    entity = make_ramp_rate_entity(prop_value=ISY_VALUE_UNKNOWN)
    assert entity.current_option is None


def test_ramp_rate_current_option_valid() -> None:
    """current_option returns RAMP_RATE_OPTIONS[value] for a valid index."""
    entity = make_ramp_rate_entity(prop_value=0)
    assert entity.current_option == RAMP_RATE_OPTIONS[0]


def test_ramp_rate_current_option_last() -> None:
    """current_option returns the last element for the highest valid index."""
    last_idx = len(RAMP_RATE_OPTIONS) - 1
    entity = make_ramp_rate_entity(prop_value=last_idx)
    assert entity.current_option == RAMP_RATE_OPTIONS[last_idx]


# ---------------------------------------------------------------------------
# ISYRampRateSelectEntity.async_select_option
# ---------------------------------------------------------------------------


async def test_ramp_rate_select_option() -> None:
    """async_select_option calls set_ramp_rate with the index of the option."""
    entity = make_ramp_rate_entity()
    entity._node.set_ramp_rate = AsyncMock()
    option = RAMP_RATE_OPTIONS[2]
    await entity.async_select_option(option)
    entity._node.set_ramp_rate.assert_awaited_once_with(2)


# ---------------------------------------------------------------------------
# ISYAuxControlIndexSelectEntity.current_option
# ---------------------------------------------------------------------------


def test_index_select_current_option_unknown() -> None:
    """current_option is None when the property value is unknown."""
    entity = make_index_select_entity(prop_value=ISY_VALUE_UNKNOWN)
    assert entity.current_option is None


def test_index_select_current_option_uom_in_states() -> None:
    """current_option looks up value in UOM_TO_STATES when UOM is known."""
    uom, states = next(iter(UOM_TO_STATES.items()))
    val, label = next(iter(states.items()))
    entity = make_index_select_entity(prop_value=val, prop_uom=uom)
    assert entity.current_option == label


def test_index_select_current_option_uom_not_in_states() -> None:
    """current_option falls back to formatted when UOM has no states table."""
    entity = make_index_select_entity(
        prop_value=5, prop_uom="UNKNOWN_UOM", prop_formatted="my_formatted"
    )
    assert entity.current_option == "my_formatted"


# ---------------------------------------------------------------------------
# ISYAuxControlIndexSelectEntity.async_select_option
# ---------------------------------------------------------------------------


async def test_index_select_option() -> None:
    """async_select_option calls send_cmd with the option's index."""
    options = ["alpha", "beta", "gamma"]
    entity = make_index_select_entity(prop_uom="99", options=options)
    entity._node.send_cmd = AsyncMock()
    await entity.async_select_option("beta")
    entity._node.send_cmd.assert_awaited_once_with("TEST_CTRL", val=1, uom="99")


# ---------------------------------------------------------------------------
# ISYBacklightSelectEntity.async_on_memory_write
# ---------------------------------------------------------------------------


def test_backlight_memory_write_filter_mismatch_ignored() -> None:
    """async_on_memory_write ignores events that don't match the backlight filter."""
    entity = make_backlight_select_entity(current_option=BACKLIGHT_INDEX[0])
    event = MagicMock()
    event.event_info = {"memory": "OTHER", "cmd1": "OTHER_CMD", "value": 1}
    entity.async_on_memory_write(event, key="test")
    entity.async_write_ha_state.assert_not_called()


def test_backlight_memory_write_same_option_ignored() -> None:
    """async_on_memory_write skips update when option matches current."""
    idx = 1
    entity = make_backlight_select_entity(current_option=BACKLIGHT_INDEX[idx])
    event = MagicMock()
    event.event_info = {**BACKLIGHT_MEMORY_FILTER, "value": idx}
    entity.async_on_memory_write(event, key="test")
    entity.async_write_ha_state.assert_not_called()


def test_backlight_memory_write_updates_option() -> None:
    """async_on_memory_write updates current_option on a new value."""
    entity = make_backlight_select_entity(current_option=BACKLIGHT_INDEX[0])
    new_idx = 2
    event = MagicMock()
    event.event_info = {**BACKLIGHT_MEMORY_FILTER, "value": new_idx}
    entity.async_on_memory_write(event, key="test")
    assert entity._attr_current_option == BACKLIGHT_INDEX[new_idx]
    entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# ISYBacklightSelectEntity.async_select_option
# ---------------------------------------------------------------------------


async def test_backlight_select_option_success() -> None:
    """async_select_option updates current_option on success."""
    entity = make_backlight_select_entity()
    entity._node.send_cmd = AsyncMock(return_value=True)
    option = BACKLIGHT_INDEX[1]
    await entity.async_select_option(option)
    entity._node.send_cmd.assert_awaited_once_with(
        CMD_BACKLIGHT, val=BACKLIGHT_INDEX.index(option), uom=ISY_UOM_INDEX
    )
    assert entity._attr_current_option == option
    entity.async_write_ha_state.assert_called_once()


async def test_backlight_select_option_failure_raises() -> None:
    """async_select_option raises HomeAssistantError when send_cmd returns falsy."""
    entity = make_backlight_select_entity()
    entity._node.send_cmd = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError):
        await entity.async_select_option(BACKLIGHT_INDEX[0])
