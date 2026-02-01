"""Tests for Ghost integration setup."""

from unittest.mock import AsyncMock, patch

from aioghost.exceptions import GhostError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None


async def test_setup_entry_auth_error(
    hass: HomeAssistant, mock_ghost_api_auth_error: AsyncMock, mock_config_entry
) -> None:
    """Test setup fails with auth error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ghost.GhostAdminAPI",
        return_value=mock_ghost_api_auth_error,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_ghost_api_connection_error: AsyncMock, mock_config_entry
) -> None:
    """Test setup retries on connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ghost.GhostAdminAPI",
        return_value=mock_ghost_api_connection_error,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test unloading config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_with_webhooks(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test setup with webhooks enabled (external URL available)."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
        patch(
            "homeassistant.components.ghost.get_url",
            return_value="https://my.home-assistant.io",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.webhooks_enabled is True
    assert len(mock_config_entry.runtime_data.ghost_webhook_ids) > 0
    mock_ghost_api.create_webhook.assert_called()


async def test_setup_entry_with_http_url_no_webhooks(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test setup with HTTP URL does not enable webhooks."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
        patch(
            "homeassistant.components.ghost.get_url",
            return_value="http://192.168.1.100:8123",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.webhooks_enabled is False
    mock_ghost_api.create_webhook.assert_not_called()


async def test_unload_entry_with_webhooks(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test unloading config entry cleans up webhooks."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
        patch(
            "homeassistant.components.ghost.get_url",
            return_value="https://my.home-assistant.io",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data.webhooks_enabled is True

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_ghost_api.delete_webhook.assert_called()


async def test_webhook_creation_failure_continues(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test that webhook creation failure doesn't break setup."""
    mock_config_entry.add_to_hass(hass)
    mock_ghost_api.create_webhook.side_effect = GhostError("Webhook limit reached")

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
        patch(
            "homeassistant.components.ghost.get_url",
            return_value="https://my.home-assistant.io",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Setup should succeed even if webhook creation fails
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_webhook_deletion_failure_continues(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test that webhook deletion failure doesn't break unload."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
        patch(
            "homeassistant.components.ghost.get_url",
            return_value="https://my.home-assistant.io",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data.webhooks_enabled is True

        # Make delete fail
        mock_ghost_api.delete_webhook.side_effect = GhostError("Not found")

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Unload should succeed even if webhook deletion fails
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
