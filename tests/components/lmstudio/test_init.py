"""Tests for LM Studio initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import lmstudio
from homeassistant.components.lmstudio import LMStudioConversationStore
from homeassistant.components.lmstudio.client import (
    LMStudioAuthError,
    LMStudioConnectionError,
    LMStudioResponseError,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from . import TEST_USER_DATA

from tests.common import MockConfigEntry


def test_conversation_store_resets_on_mismatch() -> None:
    """Test conversation store resets on model or prompt changes."""
    store = LMStudioConversationStore()
    store.set_response_id("conv-1", "model-a", "sig-a", "resp-1")

    assert store.get_previous_response_id("conv-1", "model-a", "sig-a") == "resp-1"
    assert store.get_previous_response_id("conv-1", "model-b", "sig-a") is None
    assert store.states == {}

    store.set_response_id("conv-1", "model-a", "sig-a", "resp-1")
    assert store.get_previous_response_id("conv-1", "model-a", "sig-b") is None
    assert store.states == {}


async def test_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Test setup entry fails on authentication errors."""
    entry = MockConfigEntry(domain=lmstudio.DOMAIN, data=TEST_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lmstudio.LMStudioClient.async_list_models",
            side_effect=LMStudioAuthError("bad"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await lmstudio.async_setup_entry(hass, entry)


async def test_setup_entry_response_error(hass: HomeAssistant) -> None:
    """Test setup entry raises ConfigEntryNotReady on response errors."""
    entry = MockConfigEntry(domain=lmstudio.DOMAIN, data=TEST_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lmstudio.LMStudioClient.async_list_models",
            side_effect=LMStudioResponseError("bad response"),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await lmstudio.async_setup_entry(hass, entry)


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test setup entry retries on connection errors."""
    entry = MockConfigEntry(domain=lmstudio.DOMAIN, data=TEST_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lmstudio.LMStudioClient.async_list_models",
            side_effect=LMStudioConnectionError("offline"),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await lmstudio.async_setup_entry(hass, entry)


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test setup entry succeeds and sets runtime data."""
    entry = MockConfigEntry(domain=lmstudio.DOMAIN, data=TEST_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lmstudio.LMStudioClient.async_list_models",
            return_value=[],
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ) as mock_forward,
    ):
        result = await lmstudio.async_setup_entry(hass, entry)

    assert result is True
    assert entry.runtime_data is not None
    mock_forward.assert_called_once_with(entry, lmstudio.PLATFORMS)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    entry = MockConfigEntry(domain=lmstudio.DOMAIN, data=TEST_USER_DATA)
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ) as mock_unload:
        result = await lmstudio.async_unload_entry(hass, entry)

    assert result is True
    mock_unload.assert_called_once_with(entry, lmstudio.PLATFORMS)


async def test_update_options(hass: HomeAssistant) -> None:
    """Test options update triggers reload."""
    entry = MockConfigEntry(domain=lmstudio.DOMAIN, data=TEST_USER_DATA)
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await lmstudio.async_update_options(hass, entry)

    mock_reload.assert_called_once_with(entry.entry_id)
