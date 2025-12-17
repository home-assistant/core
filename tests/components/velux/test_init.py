"""Tests for Velux integration initialization and retry behavior.

These tests verify that setup retries (ConfigEntryNotReady) are triggered
when scene or node loading fails.
"""

from __future__ import annotations

from pyvlx.exception import PyVLXException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, ConfigEntry


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
