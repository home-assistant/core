"""Tests for the Indevolt integration initialization and services."""

from unittest.mock import AsyncMock, patch

from indevolt_api import TimeOutException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_unload(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and removing a config entry."""
    await setup_integration(hass, mock_config_entry)

    # Verify the config entry is successfully loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Unload the integration
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry is properly unloaded
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_failure(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure when coordinator update fails."""
    # Simulate timeout error during coordinator initialization
    mock_indevolt.get_config.side_effect = TimeOutException

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry enters retry state due to failure
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_udp_discovery_oserror_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an OSError from create_datagram_endpoint is logged as a warning."""
    with patch(
        "asyncio.BaseEventLoop.create_datagram_endpoint",
        side_effect=OSError("Address already in use"),
    ):
        await async_setup_component(hass, "indevolt", {})
        await hass.async_block_till_done()

    assert "Failed to start UDP discovery" in caplog.text
