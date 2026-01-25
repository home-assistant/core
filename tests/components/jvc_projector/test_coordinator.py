"""Tests for JVC Projector config entry."""

from datetime import timedelta
from unittest.mock import AsyncMock

from jvcprojector import JvcProjectorAuthError, JvcProjectorTimeoutError
import pytest

from homeassistant.components.jvc_projector.coordinator import (
    INTERVAL_FAST,
    INTERVAL_SLOW,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from . import MOCK_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test coordinator update runs."""
    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=INTERVAL_SLOW.seconds + 1)
    )
    await hass.async_block_till_done()
    coordinator = mock_integration.runtime_data
    assert coordinator.update_interval == INTERVAL_SLOW


async def test_coordinator_setup_connect_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator connect error."""
    mock_device.get.side_effect = JvcProjectorTimeoutError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_setup_auth_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator auth error."""
    mock_device.get.side_effect = JvcProjectorAuthError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "mock_device",
    [{"get": {"mac": MOCK_MAC, "power": "on", "input": "hdmi-1"}}],
    indirect=True,
)
async def test_coordinator_device_on(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator changes update interval when device is on."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == INTERVAL_FAST
