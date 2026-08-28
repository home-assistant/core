"""Tests for the Bitcoin integration setup."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bitcoin.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the service device registered for blockchain.com."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device == snapshot


@pytest.mark.usefixtures("mock_exchangerates")
async def test_setup_retries_when_api_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_statistics: MagicMock
) -> None:
    """Test setup is retried when blockchain.com cannot be reached."""
    mock_statistics.side_effect = OSError("boom")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_statistics")
async def test_setup_retries_when_currency_not_quoted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exchangerates: MagicMock,
) -> None:
    """Test setup is retried when the chosen currency is no longer quoted."""
    mock_exchangerates.return_value = {}

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
