"""Tests for Velux integration initialization and retry behavior.

These tests verify that setup retries (ConfigEntryNotReady) are triggered
when scene or node loading fails.

They also verify that unloading the integration properly disconnects.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pyvlx.exception import PyVLXException

from homeassistant.components.velux.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

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


async def test_setup_auth_error(
    mock_config_entry: ConfigEntry, hass: HomeAssistant, mock_pyvlx: AsyncMock
) -> None:
    """Test that PyVLXException with auth message raises ConfigEntryAuthFailed and starts reauth flow."""

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


@pytest.mark.usefixtures("setup_integration")
async def test_reboot_gateway_service_raises_on_exception(
    hass: HomeAssistant, mock_pyvlx: AsyncMock
) -> None:
    """Test that reboot_gateway service raises HomeAssistantError on exception."""

    mock_pyvlx.reboot_gateway.side_effect = OSError("Connection failed")
    with pytest.raises(HomeAssistantError, match="Failed to reboot gateway"):
        await hass.services.async_call(
            "velux",
            "reboot_gateway",
            blocking=True,
        )

    mock_pyvlx.reboot_gateway.side_effect = PyVLXException("Reboot failed")
    with pytest.raises(HomeAssistantError, match="Failed to reboot gateway"):
        await hass.services.async_call(
            "velux",
            "reboot_gateway",
            blocking=True,
        )


async def test_reboot_gateway_service_raises_validation_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that reboot_gateway service raises ServiceValidationError when no gateway is loaded."""
    # Add the config entry but don't set it up
    mock_config_entry.add_to_hass(hass)

    # Set up the velux integration's async_setup to register the service
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="No loaded Velux gateway found"):
        await hass.services.async_call(
            "velux",
            "reboot_gateway",
            blocking=True,
        )
