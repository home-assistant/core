"""Tests for the Huum __init__."""

from unittest.mock import AsyncMock, patch

from huum.exceptions import Forbidden, NotAuthenticated
import pytest

from homeassistant import config_entries
from homeassistant.components.huum.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry


async def test_loading_and_unloading_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_huum: AsyncMock
) -> None:
    """Test loading and unloading a config entry."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("side_effect", [Forbidden, NotAuthenticated])
async def test_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test that an auth error during coordinator refresh triggers reauth."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.huum.coordinator.Huum.status",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        mock_config_entry.async_get_active_flows(hass, {config_entries.SOURCE_REAUTH})
    )
