"""Tests for Daikin Onecta schedule select entities."""

from unittest.mock import MagicMock

from daikin_onecta.models import Characteristic
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import SCHEDULE_DISABLED
from homeassistant.components.daikin_onecta.select import DaikinScheduleSelect
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
    SelectEntityCapabilityAttribute,
    SelectServiceArgument,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .platform_helpers import _execute_typed_command
from .test_climate_snapshots import _async_setup_fixture


async def test_schedule_select_updates_cached_selection(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Selecting a schedule updates the entity state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
    async_update_listeners = MagicMock(wraps=coordinator.async_update_listeners)
    coordinator.async_update_listeners = async_update_listeners

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.master_climatecontrol_schedule",
            SelectServiceArgument.OPTION: "1",
        },
        blocking=True,
    )

    state = hass.states.get("select.master_climatecontrol_schedule")
    assert state is not None
    assert state.state == "1"
    async_update_listeners.assert_called_once_with()


async def test_schedule_select_ignores_current_option(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not spend a cloud request when the selected schedule is unchanged."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    execute_command = _execute_typed_command(config_entry)
    config_entry.runtime_data.async_execute_command = execute_command
    state = hass.states.get("select.master_climatecontrol_schedule")
    assert state is not None

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: state.entity_id,
            SelectServiceArgument.OPTION: state.state,
        },
        blocking=True,
    )

    execute_command.assert_not_awaited()


async def test_schedule_select_preserves_read_only_disabled_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Keep a read-only enabled flag while changing the selected schedule."""
    await _async_setup_fixture(hass, config_entry, "gas")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
    state = hass.states.get("select.my_living_room_climatecontrol_schedule")
    assert state is not None
    assert state.state == "althermaClimateControl0"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: state.entity_id,
            SelectServiceArgument.OPTION: "althermaClimateControl1",
        },
        blocking=True,
    )

    coordinator.client.put_management_point.assert_awaited_once_with(
        next(iter(coordinator.data)),
        "1",
        "schedule/heating/current",
        {"scheduleId": "1", "enabled": False},
    )
    updated_state = hass.states.get(state.entity_id)
    assert updated_state is not None
    assert updated_state.state == "althermaClimateControl1"


async def test_schedule_select_rejects_missing_selection() -> None:
    """Reject a selection when Daikin no longer provides schedule data."""
    entity = object.__new__(DaikinScheduleSelect)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity.selection = MagicMock(return_value=None)

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_select_option("Schedule")

    assert err.value.translation_key == "schedule_selection_unavailable"


async def test_schedule_select_rejects_unadvertised_option() -> None:
    """Reject a schedule option that is not advertised by the device."""
    entity = object.__new__(DaikinScheduleSelect)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity.selection = MagicMock(return_value=MagicMock())
    entity.get_options = MagicMock(return_value=[])

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_select_option("Schedule")

    assert err.value.translation_key == "schedule_option_unavailable"


async def test_schedule_named_off_does_not_disable_schedule(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Distinguish a native schedule named off from the disabled option."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
    device = next(iter(coordinator.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.schedule is not None
    assert point.schedule.value is not None
    point.schedule.value.modes["any"].schedules["1"].name = Characteristic(value="off")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get("select.master_climatecontrol_schedule")
    assert state is not None
    assert "off" in state.attributes[SelectEntityCapabilityAttribute.OPTIONS]
    assert (
        SCHEDULE_DISABLED in state.attributes[SelectEntityCapabilityAttribute.OPTIONS]
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: state.entity_id, SelectServiceArgument.OPTION: "off"},
        blocking=True,
    )

    coordinator.client.put_management_point.assert_awaited_once_with(
        device.id,
        point.embedded_id,
        "schedule/any/current",
        {"scheduleId": "1", "enabled": True},
    )
    updated_state = hass.states.get(state.entity_id)
    assert updated_state is not None
    assert updated_state.state == "off"
