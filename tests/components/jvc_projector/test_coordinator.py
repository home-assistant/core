"""Tests for JVC Projector config entry."""

from datetime import timedelta
from unittest.mock import AsyncMock

from jvcprojector import (
    JvcProjectorCommandError,
    JvcProjectorTimeoutError,
    command as cmd,
)
import pytest

from homeassistant.components.jvc_projector.coordinator import (
    INTERVAL_FAST,
    INTERVAL_SLOW,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
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


@pytest.mark.parametrize(
    "mock_device",
    [{"fixture_override": {cmd.Power: JvcProjectorCommandError}}],
    indirect=True,
)
async def test_coordinator_setup_power_command_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test coordinator fails setup when Power command errors with no cached value."""
    assert mock_integration.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "mock_device",
    [{"fixture_override": {cmd.Input: JvcProjectorCommandError}}],
    indirect=True,
)
async def test_coordinator_command_error_keeps_other_entities_available(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test a failing command does not take every entity offline."""
    assert mock_integration.state is ConfigEntryState.LOADED

    coordinator = mock_integration.runtime_data
    assert coordinator.last_update_success is True

    power = hass.states.get("sensor.jvc_projector_status")
    assert power is not None
    assert power.state == "on"

    light_time = hass.states.get("sensor.jvc_projector_light_time")
    assert light_time is not None
    assert light_time.state != STATE_UNAVAILABLE
