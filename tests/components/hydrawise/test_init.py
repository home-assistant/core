"""Tests for the Hydrawise integration."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

from aiohttp import ClientError

from homeassistant.components.hydrawise.const import CONF_ADVANCED_SENSORS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_connect_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pydrawise: AsyncMock
) -> None:
    """Test that a connection error triggers a retry."""
    mock_pydrawise.get_user.side_effect = ClientError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_version(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test updating to the GaphQL API works."""
    mock_config_entry_legacy.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_legacy.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_legacy.state is ConfigEntryState.SETUP_ERROR

    # Make sure reauth flow has been initiated
    assert any(mock_config_entry_legacy.async_get_active_flows(hass, {"reauth"}))


async def test_update_options(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    mock_pydrawise: AsyncMock,
) -> None:
    """Test that the integration is reloaded when options are updated."""
    mock_config_entry = await mock_add_config_entry()
    # The initial load should fetch the current user, but not water use summaries.
    mock_pydrawise.get_user.assert_awaited_once()
    mock_pydrawise.get_water_use_summary.assert_not_awaited()
    mock_pydrawise.get_user.reset_mock()

    # Enable the advanced sensors option.
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options=mock_config_entry.options | {CONF_ADVANCED_SENSORS: True},
    )
    await hass.async_block_till_done()
    # With the advanced sensors option enabled, we should now query water use summaries.
    mock_pydrawise.get_user.assert_awaited_once()
    mock_pydrawise.get_water_use_summary.assert_awaited_once()
