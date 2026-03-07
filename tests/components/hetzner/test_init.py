"""Tests for the Hetzner Cloud integration setup."""

from __future__ import annotations

from unittest.mock import MagicMock

from hcloud import APIException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_hcloud")
async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_setup_entry_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcloud: MagicMock,
) -> None:
    """Test setup with connection failure raises ConfigEntryNotReady."""
    mock_hcloud.load_balancers.get_all.side_effect = APIException(
        code=500, message="Server Error", details={}
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcloud: MagicMock,
) -> None:
    """Test setup with authentication failure triggers reauth."""
    mock_hcloud.load_balancers.get_all.side_effect = APIException(
        code=401, message="Unauthorized", details={}
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, sources={"reauth"}))


@pytest.mark.usefixtures("mock_hcloud")
async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful unload of config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
