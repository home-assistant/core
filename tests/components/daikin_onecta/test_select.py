"""Tests for Daikin Onecta schedule select entities."""

from unittest.mock import MagicMock

from daikin_onecta.models import Characteristic
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.select import SCHEDULE_DISABLED
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
    SelectEntityCapabilityAttribute,
    SelectServiceArgument,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import MockOnectaClient
from .platform_helpers import _async_setup_fixture, _execute_typed_command

MASTER_SCHEDULE_ENTITY_ID = "select.master_schedule"


async def test_schedule_select_updates_cached_selection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Selecting a schedule updates the entity state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    async_update_listeners = MagicMock(wraps=coordinator.async_update_listeners)
    coordinator.async_update_listeners = async_update_listeners

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: MASTER_SCHEDULE_ENTITY_ID,
            SelectServiceArgument.OPTION: "1",
        },
        blocking=True,
    )

    state = hass.states.get(MASTER_SCHEDULE_ENTITY_ID)
    assert state is not None
    assert state.state == "1"
    async_update_listeners.assert_called_once_with()


async def test_schedule_select_ignores_current_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not spend a cloud request when the selected schedule is unchanged."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    execute_command = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute_command
    state = hass.states.get(MASTER_SCHEDULE_ENTITY_ID)
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


async def test_schedule_select_is_unavailable_when_disabled_and_read_only(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not offer schedules that cannot be enabled."""
    await _async_setup_fixture(hass, config_entry, "gas")
    coordinator = config_entry.runtime_data
    execute_command = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute_command
    state = hass.states.get("select.my_living_room_schedule")
    assert state is not None
    assert state.state == "unavailable"
    execute_command.assert_not_awaited()
    assert state.attributes["options"] == []


async def test_read_only_schedule_only_advertises_current_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not offer schedule choices that Daikin marks as read-only."""
    await _async_setup_fixture(hass, config_entry, "holidaymode")
    execute_command = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute_command
    state = hass.states.get("select.ndj_schedule")
    assert state is not None
    assert state.state == "Automatic 1"
    assert state.attributes["options"] == ["Automatic 1"]

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: state.entity_id,
                SelectServiceArgument.OPTION: "Automatic 2",
            },
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_option"
    execute_command.assert_not_awaited()


async def test_schedule_select_is_unavailable_for_read_only_disabled_schedule(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not show a schedule as active when its read-only enabled flag is off."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    device = next(iter(config_entry.runtime_data.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.schedule is not None
    assert point.schedule.value.current_mode is not None
    schedule_mode = point.schedule.value.modes[point.schedule.value.current_mode.value]
    assert schedule_mode.enabled is not None
    schedule_mode.enabled.value = False
    schedule_mode.enabled.settable = False
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(MASTER_SCHEDULE_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["options"] == []


async def test_schedule_select_rejects_missing_selection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Mark the schedule unavailable when Daikin stops providing it."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    device = next(iter(config_entry.runtime_data.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    point.schedule = None
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(MASTER_SCHEDULE_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: MASTER_SCHEDULE_ENTITY_ID,
            SelectServiceArgument.OPTION: "Schedule",
        },
        blocking=True,
    )
    mock_onecta_client.put_management_point.assert_not_awaited()


async def test_schedule_select_rejects_unadvertised_option(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Reject an option through HA that the device does not advertise."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: MASTER_SCHEDULE_ENTITY_ID,
                SelectServiceArgument.OPTION: "not-advertised",
            },
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_option"


async def test_schedule_named_off_does_not_disable_schedule(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Distinguish a native schedule named off from the disabled option."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    device = next(iter(coordinator.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.schedule is not None
    assert point.schedule.value is not None
    point.schedule.value.modes["any"].schedules["1"].name = Characteristic(value="off")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(MASTER_SCHEDULE_ENTITY_ID)
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

    mock_onecta_client.put_management_point.assert_awaited_once_with(
        device.id,
        point.embedded_id,
        "schedule/any/current",
        {"scheduleId": "1", "enabled": True},
    )
    updated_state = hass.states.get(state.entity_id)
    assert updated_state is not None
    assert updated_state.state == "off"


async def test_duplicate_schedule_names_have_unique_select_options(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Disambiguate schedule names and select the intended cloud schedule ID."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    device = next(iter(coordinator.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.schedule_state is not None
    assert point.schedule is not None and point.schedule.value is not None
    native_schedules = point.schedule.value.modes["any"].schedules
    native_schedules["1"].name = Characteristic(value="Workday")
    native_schedules["2"].name = Characteristic(value="Workday")
    selection = point.schedule_state.active_selection
    assert selection is not None
    schedules = selection.options
    native_schedules["0"].name = Characteristic(value=f"Workday ({schedules[1].id})")
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(MASTER_SCHEDULE_ENTITY_ID)
    assert state is not None
    options = state.attributes[SelectEntityCapabilityAttribute.OPTIONS]
    assert len(options) == len(set(options))
    assert f"Workday ({schedules[2].id})" in options
    assert f"Workday ({schedules[1].id} 1)" in options

    option = f"Workday ({schedules[2].id})"
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: state.entity_id,
            SelectServiceArgument.OPTION: option,
        },
        blocking=True,
    )

    mock_onecta_client.put_management_point.assert_awaited_once_with(
        device.id,
        point.embedded_id,
        "schedule/any/current",
        {"scheduleId": schedules[2].id, "enabled": True},
    )
