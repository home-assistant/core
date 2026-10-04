"""Tests for the Bitcoin integration setup."""

from unittest.mock import MagicMock

from blockchain.exchangerates import Currency
import pytest

from homeassistant.components.bitcoin.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant

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


@pytest.mark.usefixtures("mock_exchangerates")
async def test_setup_retries_when_api_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_statistics: MagicMock
) -> None:
    """Test setup is retried when blockchain.com cannot be reached."""
    mock_statistics.side_effect = OSError("boom")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_statistics")
async def test_setup_retries_when_no_rates_quoted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exchangerates: MagicMock,
) -> None:
    """Test setup is retried when blockchain.com quotes no exchange rates."""
    mock_exchangerates.return_value = {}

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_statistics")
async def test_setup_without_usd_but_with_chosen_currency(
    hass: HomeAssistant, mock_exchangerates: MagicMock
) -> None:
    """Test setup succeeds when USD is missing but the chosen currency is not."""
    mock_exchangerates.return_value = {
        "EUR": Currency(68512.4, 68515.9, 68508.9, "€", 68510.2)
    }
    entry = MockConfigEntry(domain=DOMAIN, title="Bitcoin", data={CONF_CURRENCY: "EUR"})

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
