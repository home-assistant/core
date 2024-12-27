"""Tests for the ElevenLabs TTS entity."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ConnectError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import _client_mock

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_async_client() -> Generator[AsyncMock]:
    """Override async ElevenLabs client."""
    with patch(
        "homeassistant.components.elevenlabs.AsyncElevenLabs",
        return_value=_client_mock(),
    ) as mock_async_client:
        yield mock_async_client


@pytest.fixture
def mock_setup_async_client_connect_error() -> Generator[AsyncMock]:
    """Override async ElevenLabs client."""
    client_mock = _client_mock()
    client_mock.models.get_all.side_effect = ConnectError("Unknown")
    with patch(
        "homeassistant.components.elevenlabs.AsyncElevenLabs", return_value=client_mock
    ) as mock_async_client:
        yield mock_async_client


async def test_setup(
    hass: HomeAssistant,
    mock_setup_async_client: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test entry setup without any exceptions."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state == ConfigEntryState.LOADED


async def test_setup_connect_error(
    hass: HomeAssistant,
    mock_setup_async_client_connect_error: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test entry setup with a connection error."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    # Ensure is not ready
    assert mock_entry.state == ConfigEntryState.SETUP_RETRY
