"""Test the ESPHome Dashboard init."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    # Verify coordinator is set up
    assert init_integration.runtime_data is not None

    # Test unload
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_dashboard_api_error
) -> None:
    """Test setup with connection error."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_failure(hass: HomeAssistant, mock_config_entry) -> None:
    """Test coordinator handling authentication failure triggers reauth."""
    mock_config_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    # First call succeeds for setup
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.1.0",
                    "configuration": "test_device.yaml",
                }
            ]
        }
    )

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Now make it fail with 401
        mock_api.get_devices = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=401
            )
        )

        # Trigger a coordinator refresh - this will trigger a reauth flow
        coordinator = mock_config_entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Verify reauth was triggered - check for config_entry_reauth issue
        issue_registry = ir.async_get(hass)
        issue = issue_registry.async_get_issue(
            "homeassistant",
            f"config_entry_reauth_esphome_dashboard_{mock_config_entry.entry_id}",
        )
        assert issue is not None


async def test_coordinator_non_auth_http_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test coordinator handling non-authentication HTTP error (e.g., 500)."""
    mock_config_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.request = AsyncMock(return_value=None)
    # First call succeeds for setup
    mock_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.1.0",
                    "configuration": "test_device.yaml",
                }
            ]
        }
    )

    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Now make it fail with 500 (not an auth error)
        mock_api.get_devices = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=500
            )
        )

        # Trigger a coordinator refresh - this should mark entity unavailable
        coordinator = mock_config_entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Entity should be unavailable but NO reauth issue should be created
        state = hass.states.get("update.test_device_firmware")
        assert state is not None
        assert state.state == "unavailable"

        # Verify reauth was NOT triggered (500 is not an auth error)
        issue_registry = ir.async_get(hass)
        issue = issue_registry.async_get_issue(
            "homeassistant",
            f"config_entry_reauth_esphome_dashboard_{mock_config_entry.entry_id}",
        )
        assert issue is None
