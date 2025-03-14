"""Tests for the Cambridge Audio integration."""

from unittest.mock import AsyncMock, Mock

from aiostreammagic import StreamMagicError
from aiostreammagic.models import CallbackType
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.cambridge_audio.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import mock_state_update, setup_integration

from tests.common import MockConfigEntry


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test the Cambridge Audio configuration entry not ready."""
    mock_stream_magic_client.connect = AsyncMock(side_effect=StreamMagicError())
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_stream_magic_client.connect = AsyncMock(return_value=True)


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_disconnect_reconnect_log(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)

    mock_stream_magic_client.is_connected = Mock(return_value=False)
    await mock_state_update(mock_stream_magic_client, CallbackType.CONNECTION)
    assert "Disconnected from device at 192.168.20.218" in caplog.text

    mock_stream_magic_client.is_connected = Mock(return_value=True)
    await mock_state_update(mock_stream_magic_client, CallbackType.CONNECTION)
    assert "Reconnected to device at 192.168.20.218" in caplog.text
