"""Tests for JVC Projector config entry."""

from datetime import timedelta
from unittest.mock import AsyncMock

from jvcprojector import JvcProjectorAuthError, JvcProjectorConnectError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test coordinator update runs."""
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()


async def test_coordinator_connect_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator connect error."""
    mock_device.get_state.side_effect = JvcProjectorConnectError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator auth error."""
    mock_device.get_state.side_effect = JvcProjectorAuthError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_update_interval(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator changes update interval when device is off."""
    mock_device.get_state.return_value = {"power": "standby"}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
