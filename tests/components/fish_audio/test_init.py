"""Tests for the Fish Audio entity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_async_client: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test entry setup without any exceptions."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.LOADED
    # Unload
    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "fixture",
    [
        "mock_async_client_connect_error",
        "mock_async_client_generic_error",
    ],
)
async def test_setup_retry_on_error(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_entry: MockConfigEntry,
    fixture: str,
) -> None:
    """Test entry setup with a connection error."""
    request.getfixturevalue(fixture)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure is not ready
    assert mock_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_async_client_auth_error: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test entry setup with an authentication error."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure it's in a failed state
    assert mock_entry.state == ConfigEntryState.SETUP_ERROR
