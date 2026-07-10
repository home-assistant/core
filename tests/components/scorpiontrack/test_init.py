"""Test ScorpionTrack integration setup."""

from unittest.mock import AsyncMock

from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_is_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the ScorpionTrack vehicle device is registered."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={("scorpiontrack", "101_1")})
    assert device is not None
    assert device.name == "AB12 CDE"
    assert device.manufacturer == "Volkswagen"
    assert device.model == "Golf R"


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ScorpionTrackInvalidTokenError("Invalid token"), ConfigEntryState.SETUP_ERROR),
        (
            ScorpionTrackShareUnavailableError("Share expired"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ScorpionTrackConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup with token and connection errors."""
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state
