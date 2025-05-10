"""Tests for Android TV Remote services."""

from unittest.mock import MagicMock, call

from androidtvremote2 import ConnectionClosed
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

TEST_TEXT = "Hello World"


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Android TV Remote integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service("androidtv_remote", "send_text")


async def test_send_text_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test service call to send_text."""
    await setup_integration(hass, mock_config_entry)
    response = await hass.services.async_call(
        "androidtv_remote",
        "send_text",
        {
            "config_entry_id": mock_config_entry.entry_id,
            "text": TEST_TEXT,
        },
        blocking=True,
    )
    assert response is None
    assert mock_api.send_text.mock_calls == [call(TEST_TEXT)]


async def test_send_text_service_config_entry_not_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test send_text service call with a config entry that does not exist."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(HomeAssistantError, match="not found in registry"):
        await hass.services.async_call(
            "androidtv_remote",
            "send_text",
            {
                "config_entry_id": "invalid-config-entry-id",
                "text": TEST_TEXT,
            },
            blocking=True,
        )


async def test_config_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test send_text service call with a config entry that is not loaded."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(HomeAssistantError, match="not found in registry"):
        await hass.services.async_call(
            "androidtv_remote",
            "send_text",
            {
                "config_entry_id": mock_config_entry.unique_id,
                "text": TEST_TEXT,
            },
            blocking=True,
        )


async def test_send_text_service_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test service call to send_text fails."""
    await setup_integration(hass, mock_config_entry)
    mock_api.send_text.side_effect = ConnectionClosed()

    with pytest.raises(
        HomeAssistantError, match="Connection to the Android TV device is closed"
    ):
        await hass.services.async_call(
            "androidtv_remote",
            "send_text",
            {
                "config_entry_id": mock_config_entry.entry_id,
                "text": TEST_TEXT,
            },
            blocking=True,
        )
    assert mock_api.send_text.mock_calls == [call(TEST_TEXT)]
