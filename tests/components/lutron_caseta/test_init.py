"""Tests for the Lutron Caseta integration."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MockBridge, async_setup_integration, make_mock_entry


async def test_timeout_during_connect(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a timeout during connect."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    with patch("homeassistant.components.lutron_caseta.CONNECT_TIMEOUT", 0.001):
        await async_setup_integration(
            hass,
            MockBridge,
            config_entry_id=mock_entry.entry_id,
            timeout_during_connect=True,
        )
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Timed out on connect for 1.1.1.1" in caplog.text


async def test_timeout_during_configure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a timeout during configure."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    with patch("homeassistant.components.lutron_caseta.CONFIGURE_TIMEOUT", 0.001):
        await async_setup_integration(
            hass,
            MockBridge,
            config_entry_id=mock_entry.entry_id,
            timeout_during_configure=True,
        )
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Timed out on configure for 1.1.1.1" in caplog.text


async def test_cannot_connect(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failing to connect."""
    mock_entry = make_mock_entry()
    mock_entry.add_to_hass(hass)
    await async_setup_integration(
        hass, MockBridge, config_entry_id=mock_entry.entry_id, can_connect=False
    )
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Connection failed to 1.1.1.1" in caplog.text
