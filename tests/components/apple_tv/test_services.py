"""Tests for Apple TV keyboard services."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from pyatv.const import DeviceModel, KeyboardFocusState, Protocol
from pyatv.exceptions import NotSupportedError, ProtocolError
import pytest

from homeassistant.components.apple_tv.const import ATTR_TEXT, DOMAIN
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .common import create_conf, mrp_service

from tests.common import MockConfigEntry


@pytest.fixture
def mock_atv() -> AsyncMock:
    """Create a mock Apple TV interface with keyboard support."""
    atv = AsyncMock()
    atv.keyboard = AsyncMock()
    atv.keyboard.text_focus_state = KeyboardFocusState.Focused
    atv.device_info.model = DeviceModel.Gen4K
    atv.device_info.raw_model = "AppleTV6,2"
    atv.device_info.version = "15.0"
    atv.device_info.mac = "AA:BB:CC:DD:EE:FF"
    return atv


@pytest.fixture
async def mock_config_entry(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
    mock_atv: AsyncMock,
) -> MockConfigEntry:
    """Set up Apple TV integration with mocked pyatv."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        unique_id="mrpid",
        data={
            CONF_ADDRESS: "127.0.0.1",
            CONF_NAME: "Living Room",
            "credentials": {str(Protocol.MRP.value): "mrp_creds"},
            "identifiers": ["mrpid"],
        },
    )
    entry.add_to_hass(hass)

    scan_result = create_conf("127.0.0.1", "Living Room", mrp_service())

    with (
        patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
        patch("homeassistant.components.apple_tv.connect", return_value=mock_atv),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


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
