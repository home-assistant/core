"""Tests for the EARN-E P1 Meter integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from earn_e_p1 import EarnEP1Device

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import DOMAIN, MOCK_HOST, MOCK_SERIAL

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test successful setup of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.host == MOCK_HOST
    assert mock_config_entry.runtime_data.serial == MOCK_SERIAL
    mock_listener.start.assert_awaited_once()
    mock_listener.register.assert_called_once()


async def test_setup_entry_oserror_raises_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test that OSError during setup raises ConfigEntryNotReady."""
    mock_listener.start = AsyncMock(side_effect=OSError("Address in use"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test unloading a config entry stops the shared listener."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.unregister.assert_called()
    mock_listener.stop.assert_awaited()
    assert DOMAIN not in hass.data


async def test_coordinator_handle_update(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test coordinator _handle_update processes device data."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Get the callback that was registered with the listener
    callback = mock_listener.register.call_args[0][1]

    device = EarnEP1Device(
        host=MOCK_HOST,
        serial=MOCK_SERIAL,
    )
    device.model = "P1 Meter"
    device.sw_version = "1.0.0"
    device.data = {"power_delivered": 2.5, "voltage_l1": 230.0}

    callback(device, {"raw": "data"})
    await hass.async_block_till_done()

    assert coordinator.data == {"power_delivered": 2.5, "voltage_l1": 230.0}
    assert coordinator.model == "P1 Meter"
    assert coordinator.sw_version == "1.0.0"
