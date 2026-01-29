"""Test the liebherr integration init."""

from typing import Any
from unittest.mock import MagicMock

from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_DEVICE

from tests.common import MockConfigEntry


# Test errors during initial get_devices() call in async_setup_entry
@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LiebherrAuthenticationError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (LiebherrConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "connection_error"],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    side_effect: Any,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles various error conditions."""
    mock_config_entry.add_to_hass(hass)
    mock_liebherr_client.get_devices.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


# Test errors during get_device() call in coordinator setup (after successful get_devices)
@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LiebherrAuthenticationError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (LiebherrConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "connection_error"],
)
async def test_coordinator_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test coordinator setup handles device access errors."""
    mock_config_entry.add_to_hass(hass)
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE]
    mock_liebherr_client.get_device.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test successful unload of entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
