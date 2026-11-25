"""Tests for setting up and unloading the Ablago integration."""

from unittest.mock import MagicMock

from ablago import AblagoAuthError, AblagoConnectionError, AblagoError, AblagoSSLError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(AblagoConnectionError("gone"), id="connection"),
        pytest.param(AblagoSSLError("certificate"), id="ssl"),
        pytest.param(AblagoError("HTTP 404", status=404), id="unexpected"),
    ],
)
async def test_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ablago_client: MagicMock,
    side_effect: Exception,
) -> None:
    """Test setup is retried while Ablago is not reachable."""
    mock_ablago_client.zaehler.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ablago_client: MagicMock,
) -> None:
    """Test a rejected key stops the setup."""
    mock_ablago_client.zaehler.side_effect = AblagoAuthError("401", status=401)
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
