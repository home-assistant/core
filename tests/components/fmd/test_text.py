"""Test FMD text entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.fmd.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.components.fmd.common import setup_integration


async def test_wipe_pin_validation_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test wipe PIN validation errors."""
    await setup_integration(hass, mock_fmd_api)

    # Get the entity instance
    entry = hass.config_entries.async_entries("fmd")[0]
    entity = entry.runtime_data.wipe_pin_text

    # Test non-alphanumeric
    with pytest.raises(ValueError) as excinfo:
        await entity.async_set_value("1234!")
    assert "alphanumeric" in str(excinfo.value)

    # Test non-ASCII
    with pytest.raises(ValueError) as excinfo:
        await entity.async_set_value("café")
    assert "ASCII" in str(excinfo.value)


async def test_wipe_pin_short_warning(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test warning for short wipe PIN."""
    await setup_integration(hass, mock_fmd_api)

    # Set short PIN
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_wipe_pin", "value": "12345"},
        blocking=True,
    )

    # Check for warning
    assert "Wipe PIN is less than 8 characters" in caplog.text


async def test_lock_message_update(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test lock message update."""
    await setup_integration(hass, mock_fmd_api)

    # Get the entity instance
    entry = hass.config_entries.async_entries("fmd")[0]
    entity = entry.runtime_data.lock_message_text

    # Update value
    await entity.async_set_value("Return to owner")

    # Verify state
    state = hass.states.get("text.fmd_test_user_lock_message")
    assert state is not None
    assert state.state == "Return to owner"

    # Verify config entry updated
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data["lock_message_native_value"] == "Return to owner"


async def test_wipe_pin_empty_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test wipe PIN empty error."""
    await setup_integration(hass, mock_fmd_api)

    # Get the entity instance
    entry = hass.config_entries.async_entries("fmd")[0]
    entity = entry.runtime_data.wipe_pin_text

    # Test empty PIN
    with pytest.raises(ValueError) as excinfo:
        await entity.async_set_value("")
    assert "PIN cannot be empty" in str(excinfo.value)


async def test_wipe_pin_with_spaces_validation(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test wipe PIN validation with spaces."""
    await setup_integration(hass, mock_fmd_api)

    # Try to set PIN with spaces - gets caught by alphanumeric check
    with pytest.raises(ValueError, match="alphanumeric"):
        await hass.services.async_call(
            "text",
            "set_value",
            {"entity_id": "text.fmd_test_user_wipe_pin", "value": "test 123"},
            blocking=True,
        )


async def test_lock_message_empty_validation(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test lock message validation allows empty."""
    await setup_integration(hass, mock_fmd_api)

    # Empty message should be allowed
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.fmd_test_user_lock_message", "value": ""},
        blocking=True,
    )

    state = hass.states.get("text.fmd_test_user_lock_message")
    assert state.state == ""
