"""Test script for Fluss+ integration initialization."""

from typing import Any
from unittest.mock import AsyncMock

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
    FlussDeviceOfflineError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
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


async def test_offline_device_stays_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """A 503 keeps the device but marks it offline; the rest still load."""

    async def _status(device_id: str) -> dict[str, Any]:
        if device_id == "2a303030sdj1":
            raise FlussDeviceOfflineError("offline")
        return {"status": {"internetConnected": True}}

    mock_api_client.async_get_device_status.side_effect = _status
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("button.device_1").state == STATE_UNAVAILABLE
    assert hass.states.get("button.device_2").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "exception",
    [
        FlussApiClientError("boom"),
        FlussApiClientAuthenticationError("permission revoked"),
    ],
)
async def test_failed_status_skips_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    exception: Exception,
) -> None:
    """A non-offline status error drops that device but still loads the rest."""

    async def _status(device_id: str) -> dict[str, Any]:
        if device_id == "2a303030sdj1":
            raise exception
        return {"status": {"internetConnected": True}}

    mock_api_client.async_get_device_status.side_effect = _status
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("button.device_1") is None
    assert hass.states.get("button.device_2").state == STATE_UNKNOWN
