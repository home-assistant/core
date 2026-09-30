"""Test FMD wipe device button entities."""

from unittest.mock import AsyncMock, MagicMock, patch

from fmd_api import AuthenticationError, FmdApiException, OperationError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.components.fmd.common import setup_integration


async def test_wipe_device_button_blocked(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe device button is blocked without safety switch."""
    await setup_integration(hass, mock_fmd_api)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_device"},
        blocking=True,
    )

    # Should NOT call wipe API
    mock_fmd_api.create.return_value.wipe_device.assert_not_called()


async def test_wipe_device_button_allowed(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe device button works with safety switch enabled and PIN set."""
    await setup_integration(hass, mock_fmd_api)

    # Set wipe PIN
    await hass.services.async_call(
        "text",
        "set_value",
        {
            "entity_id": "text.fmd_test_user_wipe_pin",
            "value": "MySecureWipePin123",
        },
        blocking=True,
    )

    # Enable safety switch
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Wipe button now uses device.wipe(pin=pin, confirm=True)
    mock_device = mock_fmd_api.create.return_value.device.return_value
    mock_device.wipe.assert_called_once_with(pin="MySecureWipePin123", confirm=True)


async def test_wipe_button_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe button when tracker is not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass.data
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    # Enable safety
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    # Try wipe
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Should not call API since tracker not found
    mock_fmd_api.create.return_value.send_command.assert_not_called()


async def test_wipe_button_tracker_not_found_keeps_safety_on(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """With safety on but tracker missing, wipe should not run and safety stays on."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Remove tracker from hass.data
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    # Try wipe
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_fmd_api.create.return_value.send_command.assert_not_called()
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state is not None and state.state == "on"


async def test_wipe_button_blocked_by_safety(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe button is blocked when safety switch is on."""
    await setup_integration(hass, mock_fmd_api)

    # Safety is OFF by default (disabled)
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state.state == "off"

    # Try to wipe with safety off (disabled)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Should not call send_command because safety is disabled
    mock_fmd_api.create.return_value.send_command.assert_not_called()


async def test_wipe_device_button_failure_keeps_safety_on(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """If wipe command returns False, safety should remain on."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety switch
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Return False from API
    mock_fmd_api.create.return_value.send_command.return_value = False

    # Attempt wipe
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Safety should still be ON after failure
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state is not None and state.state == "on"


async def test_wipe_device_button_auto_disables_safety(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Wipe button should auto-disable safety switch after success."""
    await setup_integration(hass, mock_fmd_api)

    # Set the wipe PIN first
    await hass.services.async_call(
        "text",
        "set_value",
        {
            "entity_id": "text.fmd_test_user_wipe_pin",
            "value": "ValidPin123",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Enable safety
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Mock device.wipe to succeed
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.return_value = None

    # Press wipe execute
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify device.wipe was called with PIN and confirm=True
    device_mock.wipe.assert_called_once_with(pin="ValidPin123", confirm=True)

    # Safety switch should be turned off by the button
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state is not None and state.state == "off"


async def test_wipe_device_button_api_error_keeps_safety_on(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """If wipe API raises, safety remains on (only disabled on success)."""
    await setup_integration(hass, mock_fmd_api)

    # Set PIN
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "ValidPin123"},
        blocking=True,
    )

    # Enable safety
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Make device.wipe raise
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.side_effect = RuntimeError("wipe failed")

    # Press wipe execute - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )

    await hass.async_block_till_done()

    # Safety should still be on
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state is not None and state.state == "on"


async def test_wipe_device_button_authentication_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe button raises HomeAssistantError on AuthenticationError."""
    await setup_integration(hass, mock_fmd_api)

    # Set PIN and enable safety
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "ValidPin123"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.side_effect = AuthenticationError("auth failed")

    with pytest.raises(HomeAssistantError, match="Authentication failed"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )


async def test_wipe_device_button_operation_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe button raises HomeAssistantError on OperationError."""
    await setup_integration(hass, mock_fmd_api)

    # Set PIN and enable safety
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "ValidPin123"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.side_effect = OperationError("connection failed")

    with pytest.raises(HomeAssistantError, match="Wipe command failed"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )


async def test_wipe_device_button_fmd_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe button raises HomeAssistantError on FmdApiException."""
    await setup_integration(hass, mock_fmd_api)

    # Set PIN and enable safety
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "ValidPin123"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.side_effect = FmdApiException("API failed")

    with pytest.raises(HomeAssistantError, match="Wipe command failed"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )


async def test_wipe_device_button_unexpected_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe button raises HomeAssistantError on unexpected Exception."""
    await setup_integration(hass, mock_fmd_api)

    # Set PIN and enable safety
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "ValidPin123"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.side_effect = ValueError("unexpected")

    with pytest.raises(HomeAssistantError, match="Wipe command failed"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )


async def test_wipe_button_invalid_pin(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test wipe button blocks invalid PIN."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety switch
    hass.states.async_set("switch.fmd_test_user_wipe_safety_switch", "on")

    # Mock PIN text entity with invalid PIN (contains space)
    mock_text = MagicMock()
    mock_text.native_value = "invalid pin"
    hass.config_entries.async_entries("fmd")[0].runtime_data.wipe_pin_text = mock_text

    # Patch Device
    with patch("homeassistant.components.fmd.button.Device") as mock_device_cls:
        mock_device = mock_device_cls.return_value

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )

        # Verify wipe was NOT called
        mock_device.wipe.assert_not_called()
        assert "Invalid wipe PIN" in caplog.text


async def test_wipe_button_missing_pin_entity(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test wipe button blocks when PIN entity is missing."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety switch
    hass.states.async_set("switch.fmd_test_user_wipe_safety_switch", "on")

    # Remove PIN entity
    hass.config_entries.async_entries("fmd")[0].runtime_data.wipe_pin_text = None

    # Patch Device
    with patch("homeassistant.components.fmd.button.Device") as mock_device_cls:
        mock_device = mock_device_cls.return_value

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )

        # Verify wipe was NOT called
        mock_device.wipe.assert_not_called()
        assert "Wipe PIN entity not found" in caplog.text


async def test_wipe_button_empty_pin(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test wipe button blocks when PIN is empty."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety switch
    hass.states.async_set("switch.fmd_test_user_wipe_safety_switch", "on")

    # Mock PIN text entity with empty PIN
    mock_text = MagicMock()
    mock_text.native_value = ""
    hass.config_entries.async_entries("fmd")[0].runtime_data.wipe_pin_text = mock_text

    # Patch Device
    with patch("homeassistant.components.fmd.button.Device") as mock_device_cls:
        mock_device = mock_device_cls.return_value

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_wipe_execute"},
            blocking=True,
        )

        # Verify wipe was NOT called
        mock_device.wipe.assert_not_called()
        assert "Wipe PIN is not set" in caplog.text


async def test_wipe_button_invalid_pin_validation_fails(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Wipe button with invalid PIN that fails validation."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )

    # Set invalid PIN (contains special characters) - text entity will raise ValueError
    with pytest.raises(ValueError, match="alphanumeric"):
        await hass.services.async_call(
            "text",
            "set_value",
            {"entity_id": "text.fmd_test_user_wipe_pin", "value": "Pin@123!"},
            blocking=True,
        )


async def test_wipe_button_tracker_missing_after_validation(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Wipe button when tracker missing after PIN validation."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety and set valid PIN
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "ValidPin123"},
        blocking=True,
    )

    # Remove tracker from hass.data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.tracker = None

    # Try to wipe
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )

    # Should not call wipe API
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.assert_not_called()


async def test_wipe_button_safety_switch_missing_after_success(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Wipe succeeds but safety_switch missing when trying to disable it."""
    await setup_integration(hass, mock_fmd_api)

    # Enable safety and set valid PIN
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "SecurePin456"},
        blocking=True,
    )

    # Remove safety switch from hass.data before wipe
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.wipe_safety_switch = None

    # Mock successful wipe
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe.return_value = None

    # Execute wipe - should succeed but not crash when safety_switch missing
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )

    # Verify wipe was called
    device_mock.wipe.assert_called_once_with(pin="SecurePin456", confirm=True)


async def test_switch_wipe_safety_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe safety switch when tracker not found (for logging)."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.tracker = None

    # Turn on the wipe safety switch (should still work, just logs differently)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_wipe_safety_switch"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify it's on
    state = hass.states.get("switch.fmd_test_user_wipe_safety_switch")
    assert state.state == "on"


async def test_switch_wipe_safety_auto_disable_cancelled_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test wipe safety auto-disable handles CancelledError gracefully."""
    await setup_integration(hass, mock_fmd_api)

    # Get the wipe safety switch
    entry = hass.config_entries.async_entries("fmd")[0]
    safety_switch = entry.runtime_data.wipe_safety_switch

    # Turn on the switch (starts auto-disable task)
    await safety_switch.async_turn_on()
    await hass.async_block_till_done()

    # Verify task was created
    assert safety_switch._auto_disable_task is not None

    # Turn off the switch (cancels the task)
    await safety_switch.async_turn_off()
    await hass.async_block_till_done()

    # Task should be cancelled and set to None
    assert safety_switch._auto_disable_task is None
    assert safety_switch.is_on is False
