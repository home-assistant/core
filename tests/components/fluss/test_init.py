"""Test script for Fluss+ integration initialization."""

from unittest.mock import AsyncMock

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test the Fluss configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_api_client.async_get_devices.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (FlussApiClientAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (FlussApiClientCommunicationError, ConfigEntryState.SETUP_RETRY),
        (FlussApiClientError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_async_setup_entry_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test that an authentication error during setup leads to SETUP_ERROR state."""
    mock_api_client.async_get_devices.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_status_authentication_error_marks_device_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test that an auth error from a per-device status call marks the device offline."""
    mock_api_client.async_get_device_status.side_effect = (
        FlussApiClientAuthenticationError("permission revoked")
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("button.device_1").state == STATE_UNAVAILABLE
    assert hass.states.get("button.device_2").state == STATE_UNAVAILABLE
