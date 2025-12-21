"""Tests for Velux integration initialization and retry behavior.

These tests verify that setup retries (ConfigEntryNotReady) are triggered
when scene or node loading fails.

They also verify that unloading the integration properly disconnects.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pyvlx.exception import PyVLXException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, ConfigEntry, MockConfigEntry


async def test_setup_retry_on_nodes_failure(
    mock_config_entry: ConfigEntry, hass: HomeAssistant, mock_pyvlx: AsyncMock
) -> None:
    """Test that a failure loading nodes triggers setup retry.

    The integration loads scenes first, then nodes. If loading raises PyVLXException,
    (which could have a multitude of reasons, unfortunately there are no specialized
    exceptions that give a reason), the ConfigEntry should enter SETUP_RETRY.
    """

    mock_pyvlx.load_nodes.side_effect = PyVLXException("nodes boom")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_pyvlx.load_scenes.assert_awaited_once()
    mock_pyvlx.load_nodes.assert_awaited_once()


async def test_setup_retry_on_oserror_during_scenes(
    mock_config_entry: ConfigEntry, hass: HomeAssistant, mock_pyvlx: AsyncMock
) -> None:
    """Test that OSError during scene loading triggers setup retry.

    OSError typically indicates network/connection issues when the gateway
    refuses connections or is unreachable.
    """

    mock_pyvlx.load_scenes.side_effect = OSError("Connection refused")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_pyvlx.load_scenes.assert_awaited_once()
    mock_pyvlx.load_nodes.assert_not_called()


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.COVER


@pytest.mark.usefixtures("setup_integration")
async def test_unload_calls_disconnect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pyvlx
) -> None:
    """Test that unloading the config entry disconnects from the gateway."""

    # Unload the entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify disconnect was called
    mock_pyvlx.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("setup_integration")
async def test_unload_does_not_disconnect_if_platform_unload_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pyvlx
) -> None:
    """Test that disconnect is not called if platform unload fails."""

    # Mock platform unload to fail
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify unload failed
    assert result is False

    # Verify disconnect was NOT called since platform unload failed
    mock_pyvlx.disconnect.assert_not_awaited()
