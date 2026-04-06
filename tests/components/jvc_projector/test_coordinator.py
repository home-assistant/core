"""Tests for JVC Projector config entry."""

from datetime import timedelta
from unittest.mock import AsyncMock

from jvcprojector import JvcProjectorTimeoutError, command as cmd
import pytest

from homeassistant.components.jvc_projector.coordinator import (
    INTERVAL_FAST,
    INTERVAL_SLOW,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "mock_device",
    [{"fixture": "standby"}],
    indirect=True,
)
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


async def test_coordinator_device_on(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test coordinator changes update interval when device is on."""
    coordinator = mock_integration.runtime_data
    assert coordinator.update_interval == INTERVAL_FAST


@pytest.mark.parametrize(
    "mock_device",
    [{"fixture_override": {cmd.Power: JvcProjectorTimeoutError}}],
    indirect=True,
)
async def test_coordinator_setup_connect_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test coordinator connect error."""
    assert mock_integration.state is ConfigEntryState.SETUP_RETRY
