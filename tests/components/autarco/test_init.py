"""Test the Autarco init module."""

from __future__ import annotations

from unittest.mock import AsyncMock

from autarco import AutarcoAuthenticationError, AutarcoConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_autarco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_autarco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Autarco configuration entry not ready."""
    mock_autarco_client.get_account.side_effect = AutarcoConnectionError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_exception(
    hass: HomeAssistant,
    mock_autarco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    mock_config_entry.add_to_hass(hass)
    mock_autarco_client.get_site.side_effect = AutarcoAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
