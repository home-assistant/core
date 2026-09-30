"""Test FMD basic button entities (Location, Ring, Lock, Capture)."""

from unittest.mock import AsyncMock

from fmd_api import AuthenticationError, FmdApiException, OperationError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.components.fmd.common import setup_integration


async def test_location_update_button(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test location update button."""
    await setup_integration(hass, mock_fmd_api)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_location_update"},
        blocking=True,
    )

    mock_fmd_api.create.return_value.request_location.assert_called_once()


async def test_location_update_uses_selected_provider_gps(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Selecting GPS Only should call request_location with provider='gps'."""
    await setup_integration(hass, mock_fmd_api)

    # Change select option to GPS Only (Accurate)
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.fmd_test_user_location_source",
            "option": "GPS Only (Accurate)",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Press location update
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_location_update"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify provider mapping
    assert mock_fmd_api.create.return_value.request_location.called
    kwargs = mock_fmd_api.create.return_value.request_location.call_args.kwargs
    assert kwargs.get("provider") == "gps"


async def test_location_update_default_provider(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Location update uses provider='all' when default option is selected."""
    await setup_integration(hass, mock_fmd_api)

    # By default the select is "All Providers (Default)"
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_location_update"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Ensure provider default was used
    mock_fmd_api.create.return_value.request_location.assert_called()
    kwargs = mock_fmd_api.create.return_value.request_location.call_args.kwargs
    assert kwargs.get("provider") == "all"


async def test_location_update_missing_select_entity(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """If location source select entity is missing, warning path executes."""
    await setup_integration(hass, mock_fmd_api)

    # Remove the select entity to force warning branch
    hass.states.async_remove("select.fmd_test_user_location_source")

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_location_update"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Ensure request_location still called with default provider 'all'
    assert mock_fmd_api.create.return_value.request_location.called
    kwargs = mock_fmd_api.create.return_value.request_location.call_args.kwargs
    assert kwargs.get("provider") == "all"


async def test_location_update_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test location update when tracker is not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass.data
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_location_update"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Should handle gracefully - API should not be called
    mock_fmd_api.create.return_value.request_location.assert_not_called()


async def test_ring_button(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ring button."""
    await setup_integration(hass, mock_fmd_api)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_volume_ring_device"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_fmd_api.create.return_value.send_command.assert_called_once_with("ring")


async def test_ring_button_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ring button handles API errors gracefully."""
    await setup_integration(hass, mock_fmd_api)

    # Mock API to raise error
    mock_fmd_api.create.return_value.send_command.side_effect = RuntimeError(
        "API error"
    )

    # The button should wrap the error in HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Ring command failed"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_volume_ring_device"},
            blocking=True,
        )

    await hass.async_block_till_done()
    mock_fmd_api.create.return_value.send_command.assert_called_once_with("ring")


async def test_ring_button_returns_false(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """If ring command returns False, it should just log a warning."""
    await setup_integration(hass, mock_fmd_api)

    mock_fmd_api.create.return_value.send_command.return_value = False

    # Should not raise, just log warning
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_volume_ring_device"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_fmd_api.create.return_value.send_command.assert_called_once_with("ring")


async def test_lock_button(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test lock button."""
    await setup_integration(hass, mock_fmd_api)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Lock button now uses device.lock() with optional message
    mock_fmd_api.create.return_value.device.return_value.lock.assert_called_once()


async def test_lock_button_with_message(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test lock button works with optional message."""
    await setup_integration(hass, mock_fmd_api)

    # Set a lock message
    await hass.services.async_call(
        "text",
        "set_value",
        {
            "entity_id": "text.fmd_test_user_lock_message",
            "value": "Device has been locked remotely",
        },
        blocking=True,
    )

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify lock was called with the message
    mock_device = mock_fmd_api.create.return_value.device.return_value
    mock_device.lock.assert_called_once_with(message="Device has been locked remotely")


async def test_lock_button_exceptions(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test lock button handles exceptions gracefully (logs but doesn't raise)."""
    await setup_integration(hass, mock_fmd_api)

    mock_device = mock_fmd_api.create.return_value.device.return_value

    # Test AuthenticationError
    mock_device.lock.side_effect = AuthenticationError("Auth Error")
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )

    # Test OperationError
    mock_device.lock.side_effect = OperationError("Op Error")
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )

    # Test FmdApiException
    mock_device.lock.side_effect = FmdApiException("API Error")
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )

    # Test generic Exception
    mock_device.lock.side_effect = Exception("Generic Error")
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )


async def test_capture_front_button(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test capture front photo button."""
    await setup_integration(hass, mock_fmd_api)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_front"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_fmd_api.create.return_value.take_picture.assert_called_once_with("front")


async def test_capture_rear_button(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test capture rear photo button."""
    await setup_integration(hass, mock_fmd_api)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_rear"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_fmd_api.create.return_value.take_picture.assert_called_once_with("back")


async def test_capture_photo_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test capture photo button handles API errors gracefully."""
    await setup_integration(hass, mock_fmd_api)

    # Mock API to raise error
    mock_fmd_api.create.return_value.take_picture.side_effect = RuntimeError(
        "API error"
    )

    # Should not raise, just log error
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_front"},
        blocking=True,
    )

    await hass.async_block_till_done()
    mock_fmd_api.create.return_value.take_picture.assert_called_once_with("front")


async def test_capture_returns_false(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """If take_picture returns False, it should be handled without crash."""
    await setup_integration(hass, mock_fmd_api)

    mock_fmd_api.create.return_value.take_picture.return_value = False

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_front"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_fmd_api.create.return_value.take_picture.assert_called_once_with("front")
