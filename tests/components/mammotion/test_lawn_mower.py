"""Test for the Mammotion lawn_mower platform."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from pymammotion.utility.constant.device_constant import WorkMode
import pytest

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntityFeature,
)
from homeassistant.components.mammotion import MammotionDevices
from homeassistant.components.mammotion.const import COMMAND_EXCEPTIONS, DOMAIN
from homeassistant.components.mammotion.lawn_mower import (
    MammotionLawnMowerEntity,
    async_setup_entry,
    get_entity_attribute,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_get_entity_attribute(hass: HomeAssistant) -> None:
    """Test the get_entity_attribute function."""
    # Set up a mock state
    hass.states.async_set("sensor.test", "on", {"test_attribute": "test_value"})

    # Test getting an existing attribute
    result = get_entity_attribute(hass, "sensor.test", "test_attribute")
    assert result == "test_value"

    # Test getting a non-existent attribute
    result = get_entity_attribute(hass, "sensor.test", "non_existent")
    assert result is None

    # Test getting an attribute from a non-existent entity
    result = get_entity_attribute(hass, "sensor.non_existent", "test_attribute")
    assert result is None


async def test_async_setup_entry(hass: HomeAssistant, mock_mower_coordinator) -> None:
    """Test setting up the lawn mower platform."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="test-unique-id",
    )
    config_entry.runtime_data = MammotionDevices(
        mowers=[MagicMock(reporting_coordinator=mock_mower_coordinator)]
    )

    with patch(
        "homeassistant.components.mammotion.lawn_mower.MammotionLawnMowerEntity"
    ):
        await async_setup_entry(hass, config_entry, Mock())


async def test_lawn_mower_entity_init(mock_mower_coordinator) -> None:
    """Test initializing the lawn mower entity."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    assert entity._attr_name is None
    assert entity._attr_supported_features == (
        LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
    )


async def test_lawn_mower_activity_mowing(mock_mower_coordinator) -> None:
    """Test the activity property when mowing."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_WORKING

    assert entity.activity == LawnMowerActivity.MOWING


async def test_lawn_mower_activity_paused(mock_mower_coordinator) -> None:
    """Test the activity property when paused."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    # Test MODE_PAUSE
    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_PAUSE
    assert entity.activity == LawnMowerActivity.PAUSED

    # Test MODE_READY with charge_state 0
    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_READY
    mock_mower_coordinator.data.report_data.dev.charge_state = 0
    assert entity.activity == LawnMowerActivity.PAUSED


async def test_lawn_mower_activity_docked(mock_mower_coordinator) -> None:
    """Test the activity property when docked."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_READY
    mock_mower_coordinator.data.report_data.dev.charge_state = 1

    assert entity.activity == LawnMowerActivity.DOCKED


async def test_lawn_mower_activity_returning(mock_mower_coordinator) -> None:
    """Test the activity property when returning."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_RETURNING

    assert entity.activity == LawnMowerActivity.RETURNING


async def test_lawn_mower_activity_error(mock_mower_coordinator) -> None:
    """Test the activity property when in error state."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_LOCK

    assert entity.activity == LawnMowerActivity.ERROR


async def test_lawn_mower_activity_none(mock_mower_coordinator) -> None:
    """Test the activity property returns None for unknown states."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    # Test None sys_status
    mock_mower_coordinator.data.report_data.dev.sys_status = None
    assert entity.activity is None

    # Test unhandled sys_status
    mock_mower_coordinator.data.report_data.dev.sys_status = 999
    assert entity.activity is None


async def test_async_dock(mock_mower_coordinator) -> None:
    """Test the async_dock method."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_mower_coordinator.async_send_command = AsyncMock()
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    # Test working mode
    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_WORKING
    mock_mower_coordinator.data.report_data.dev.charge_state = 0

    await entity.async_dock()

    assert mock_mower_coordinator.async_send_command.call_count == 2
    assert (
        mock_mower_coordinator.async_send_command.call_args_list[0][0][0]
        == "pause_execute_task"
    )
    assert (
        mock_mower_coordinator.async_send_command.call_args_list[1][0][0]
        == "return_to_dock"
    )
    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 1


async def test_async_dock_returning(mock_mower_coordinator) -> None:
    """Test the async_dock method when already returning."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_mower_coordinator.async_send_command = AsyncMock()
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_RETURNING
    mock_mower_coordinator.data.report_data.dev.charge_state = 0

    await entity.async_dock()

    assert mock_mower_coordinator.async_send_command.call_count == 1
    assert (
        mock_mower_coordinator.async_send_command.call_args_list[0][0][0]
        == "cancel_return_to_dock"
    )
    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 1


async def test_async_dock_ready(mock_mower_coordinator) -> None:
    """Test the async_dock method when device is ready."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_mower_coordinator.async_send_command = AsyncMock()
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_READY
    mock_mower_coordinator.data.report_data.dev.charge_state = 0

    await entity.async_dock()

    assert mock_mower_coordinator.async_send_command.call_count == 1
    assert (
        mock_mower_coordinator.async_send_command.call_args_list[0][0][0]
        == "return_to_dock"
    )
    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 1


async def test_async_dock_not_ready(mock_mower_coordinator) -> None:
    """Test the async_dock method when device is not ready."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    mock_mower_coordinator.data.report_data.dev.sys_status = None

    with patch.object(mock_mower_coordinator, "async_send_command"):
        with pytest.raises(HomeAssistantError) as exc_info:
            await entity.async_dock()
        error = exc_info.value
        assert error.translation_domain


async def test_async_dock_command_exception(mock_mower_coordinator) -> None:
    """Test the async_dock method with command exceptions."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_error = COMMAND_EXCEPTIONS[0]("Test error")
    mock_mower_coordinator.async_send_command = AsyncMock(side_effect=mock_error)
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_WORKING
    mock_mower_coordinator.data.report_data.dev.charge_state = 0

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_dock()
    error = exc_info.value
    assert error.translation_domain == DOMAIN
    assert error.translation_key == "pause_failed"

    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 1


async def test_async_pause(mock_mower_coordinator) -> None:
    """Test the async_pause method."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_mower_coordinator.async_send_command = AsyncMock()
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    # Test working mode
    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_WORKING

    await entity.async_pause()

    assert mock_mower_coordinator.async_send_command.call_count == 1
    assert (
        mock_mower_coordinator.async_send_command.call_args_list[0][0][0]
        == "pause_execute_task"
    )
    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 1


async def test_async_pause_returning(mock_mower_coordinator) -> None:
    """Test the async_pause method when returning."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_mower_coordinator.async_send_command = AsyncMock()
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_RETURNING

    await entity.async_pause()

    assert mock_mower_coordinator.async_send_command.call_count == 1
    assert (
        mock_mower_coordinator.async_send_command.call_args_list[0][0][0]
        == "cancel_return_to_dock"
    )
    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 1


async def test_async_pause_not_ready(mock_mower_coordinator) -> None:
    """Test the async_pause method when device is not ready."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)

    mock_mower_coordinator.data.report_data.dev.sys_status = None

    with patch.object(mock_mower_coordinator, "async_send_command"):
        with pytest.raises(HomeAssistantError) as exc_info:
            await entity.async_pause()
        error = exc_info.value
        assert error.translation_domain == DOMAIN
        assert error.translation_key == "device_not_ready"


async def test_async_pause_not_working_or_returning(mock_mower_coordinator) -> None:
    """Test the async_pause method when not in working or returning mode."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_mower_coordinator.async_send_command = AsyncMock()
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_READY

    # Should not call any commands
    await entity.async_pause()

    assert mock_mower_coordinator.async_send_command.call_count == 0
    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 0


async def test_async_pause_command_exception(mock_mower_coordinator) -> None:
    """Test the async_pause method with command exceptions."""
    entity = MammotionLawnMowerEntity(mock_mower_coordinator)
    mock_error = COMMAND_EXCEPTIONS[0]("Test error")
    mock_mower_coordinator.async_send_command = AsyncMock(side_effect=mock_error)
    mock_mower_coordinator.api.async_request_iot_sync = AsyncMock()

    mock_mower_coordinator.data.report_data.dev.sys_status = WorkMode.MODE_WORKING

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_pause()
    error = exc_info.value
    assert error.translation_domain == DOMAIN
    assert error.translation_key == "pause_failed"

    assert mock_mower_coordinator.api.async_request_iot_sync.call_count == 1
