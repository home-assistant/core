"""Tests for Apple TV keyboard services."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyatv.const import KeyboardFocusState
import pytest

from homeassistant.components.apple_tv.const import ATTR_TEXT, DOMAIN
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


@pytest.fixture
def mock_manager() -> MagicMock:
    """Create a mock AppleTVManager."""
    manager = MagicMock()
    manager.atv = MagicMock()
    manager.atv.keyboard = AsyncMock()
    manager.atv.keyboard.text_focus_state = KeyboardFocusState.Focused
    return manager


@pytest.fixture
async def mock_config_entry(
    hass: HomeAssistant, mock_manager: MagicMock
) -> str:
    """Set up a mock config entry and return its entry_id."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        data={},
        disabled_by=None,
        domain=DOMAIN,
        minor_version=1,
        options={},
        source="user",
        title="Living Room",
        unique_id="test_unique_id",
        version=1,
    )
    entry.runtime_data = mock_manager
    entry._async_set_state(hass, ConfigEntry.State.LOADED, None)
    hass.config_entries._entries[entry.entry_id] = entry
    hass.config_entries._domain_index.setdefault(DOMAIN, []).append(entry.entry_id)

    # Register services
    from homeassistant.components.apple_tv.services import async_setup_services

    async_setup_services(hass)

    return entry.entry_id


async def test_set_keyboard_text(
    hass: HomeAssistant, mock_config_entry: str, mock_manager: MagicMock
) -> None:
    """Test setting keyboard text."""
    await hass.services.async_call(
        DOMAIN,
        "set_keyboard_text",
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry, ATTR_TEXT: "Star Wars"},
        blocking=True,
    )
    mock_manager.atv.keyboard.text_set.assert_called_once_with("Star Wars")


async def test_append_keyboard_text(
    hass: HomeAssistant, mock_config_entry: str, mock_manager: MagicMock
) -> None:
    """Test appending keyboard text."""
    await hass.services.async_call(
        DOMAIN,
        "append_keyboard_text",
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry, ATTR_TEXT: " Episode IV"},
        blocking=True,
    )
    mock_manager.atv.keyboard.text_append.assert_called_once_with(" Episode IV")


async def test_clear_keyboard_text(
    hass: HomeAssistant, mock_config_entry: str, mock_manager: MagicMock
) -> None:
    """Test clearing keyboard text."""
    await hass.services.async_call(
        DOMAIN,
        "clear_keyboard_text",
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry},
        blocking=True,
    )
    mock_manager.atv.keyboard.text_clear.assert_called_once()


async def test_set_keyboard_text_not_connected(
    hass: HomeAssistant, mock_config_entry: str, mock_manager: MagicMock
) -> None:
    """Test error when device is not connected."""
    mock_manager.atv = None
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_keyboard_text",
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry, ATTR_TEXT: "test"},
            blocking=True,
        )


async def test_set_keyboard_text_not_focused(
    hass: HomeAssistant, mock_config_entry: str, mock_manager: MagicMock
) -> None:
    """Test error when keyboard is not focused."""
    mock_manager.atv.keyboard.text_focus_state = KeyboardFocusState.Unfocused
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_keyboard_text",
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry, ATTR_TEXT: "test"},
            blocking=True,
        )
