"""Tests for Ghost diagnostics."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.ghost.const import CONF_ADMIN_API_KEY, CONF_API_URL
from homeassistant.components.ghost.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test diagnostics returns expected data with redacted API key."""
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

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Check structure
    assert "entry_data" in diagnostics
    assert "coordinator_data" in diagnostics
    assert "last_update_success" in diagnostics
    assert "webhooks_enabled" in diagnostics
    assert "webhook_count" in diagnostics

    # Check API key is redacted
    assert diagnostics["entry_data"][CONF_ADMIN_API_KEY] == "**REDACTED**"

    # Check API URL is not redacted
    assert CONF_API_URL in diagnostics["entry_data"]
    assert diagnostics["entry_data"][CONF_API_URL] != "**REDACTED**"

    # Check coordinator data is present
    assert diagnostics["coordinator_data"] is not None
    assert diagnostics["last_update_success"] is True
