"""Tests for Velux integration initialization and retry behavior.

These tests verify that setup retries (ConfigEntryNotReady) are triggered
when scene or node loading fails.

They also verify that unloading the integration properly disconnects.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pyvlx.exception import PyVLXException

from homeassistant.components.velux.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from tests.common import ConfigEntry, MockConfigEntry


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


async def test_setup_auth_error(
    mock_config_entry: ConfigEntry, hass: HomeAssistant, mock_pyvlx: AsyncMock
) -> None:
    """Test PyVLXException with auth message raises ConfigEntryAuthFailed."""

    mock_pyvlx.load_scenes.side_effect = PyVLXException(
        "Login to KLF 200 failed, check credentials"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ConfigEntryAuthFailed results in SETUP_ERROR state
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    mock_pyvlx.load_scenes.assert_awaited_once()
    mock_pyvlx.load_nodes.assert_not_called()


async def test_setup_uses_preconnected_pyvlx_from_config_flow(
    hass: HomeAssistant, mock_pyvlx: AsyncMock
) -> None:
    """Test that setup reuses the PyVLX instance from config flow without disconnecting.

    The config flow connects once; setup should reuse that instance without
    disconnecting and reconnecting, preventing an unnecessary disconnect/reboot
    cycle between connection validation and integration start.
    """
    with patch("homeassistant.components.velux.PLATFORMS", []):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "127.0.0.1",
                CONF_PASSWORD: "NotAStrongPassword",
            },
        )
        await hass.async_block_till_done()

    assert result["result"].state is ConfigEntryState.LOADED

    # connect was called exactly once (by config flow), setup must not call it again
    mock_pyvlx.connect.assert_awaited_once()
    # ensure_connected was called once (by async_setup_entry)
    mock_pyvlx.ensure_connected.assert_awaited_once()
    # The gateway must not be disconnected between config flow and setup
    mock_pyvlx.disconnect.assert_not_awaited()
    mock_pyvlx.load_scenes.assert_awaited_once()
    mock_pyvlx.load_nodes.assert_awaited_once()


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
