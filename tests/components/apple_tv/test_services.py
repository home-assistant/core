"""Tests for Apple TV keyboard services."""

from unittest.mock import AsyncMock, PropertyMock, patch

from pyatv.const import KeyboardFocusState
from pyatv.exceptions import NotSupportedError, ProtocolError
import pytest

from homeassistant.components.apple_tv.const import ATTR_TEXT, DOMAIN
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_set_keyboard_text(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """Test setting keyboard text."""
    await hass.services.async_call(
        DOMAIN,
        "set_keyboard_text",
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, ATTR_TEXT: "Star Wars"},
        blocking=True,
    )
    mock_atv.keyboard.text_set.assert_called_once_with("Star Wars")


async def test_append_keyboard_text(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """Test appending keyboard text."""
    await hass.services.async_call(
        DOMAIN,
        "append_keyboard_text",
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_TEXT: " Episode IV",
        },
        blocking=True,
    )
    mock_atv.keyboard.text_append.assert_called_once_with(" Episode IV")


async def test_clear_keyboard_text(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """Test clearing keyboard text."""
    await hass.services.async_call(
        DOMAIN,
        "clear_keyboard_text",
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
    )
    mock_atv.keyboard.text_clear.assert_called_once()


async def test_set_keyboard_text_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """Test error when device is not connected."""
    mock_config_entry.runtime_data.atv = None
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_keyboard_text",
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, ATTR_TEXT: "test"},
            blocking=True,
        )


async def test_set_keyboard_text_not_focused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """Test error when keyboard is not focused."""
    mock_atv.keyboard.text_focus_state = KeyboardFocusState.Unfocused
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_keyboard_text",
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, ATTR_TEXT: "test"},
            blocking=True,
        )


async def test_set_keyboard_text_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """Test error when keyboard is not supported by device."""
    with (
        patch.object(
            type(mock_atv.keyboard),
            "text_focus_state",
            new_callable=PropertyMock,
            side_effect=NotSupportedError("text_focus_state is not supported"),
            create=True,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_keyboard_text",
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, ATTR_TEXT: "test"},
            blocking=True,
        )


async def test_set_keyboard_text_protocol_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atv: AsyncMock,
) -> None:
    """Test error when text_set raises a protocol error."""
    mock_atv.keyboard.text_set.side_effect = ProtocolError("send failed")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_keyboard_text",
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, ATTR_TEXT: "test"},
            blocking=True,
        )
