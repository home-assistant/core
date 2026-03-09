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
    [{"fixture_override": {cmd.PictureMode: "hdr10"}}],
    indirect=True,
)
async def test_coordinator_deferred_command_dependencies(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test deferred commands are evaluated from both new and existing state."""
    coordinator = mock_integration.runtime_data
    commands = {cmd.Hdr, cmd.HdrProcessing, cmd.PictureMode}

    # First pass: dependency (Hdr) is present in new_state.
    new_state = await coordinator._get_device_state(commands)
    assert new_state[cmd.Hdr] == cmd.Hdr.HDR
    assert new_state[cmd.PictureMode] == "hdr10"
    assert new_state[cmd.HdrProcessing] == "static"
    coordinator.state.update(new_state)

    # Second pass: dependency should be read from coordinator.state when unchanged.
    await coordinator._get_device_state(commands)


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
