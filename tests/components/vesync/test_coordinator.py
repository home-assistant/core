"""Tests for the VeSync coordinator."""

from datetime import timedelta
import time
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pyvesync import VeSync
from pyvesync.utils.errors import VeSyncError

from homeassistant.components.vesync.const import UPDATE_INTERVAL_ENERGY
from homeassistant.components.vesync.coordinator import (
    COMMAND_GRACE_PERIOD,
    VeSyncDataCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_should_update_energy(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test energy data is only refreshed once per interval."""
    coordinator = VeSyncDataCoordinator(hass, config_entry, manager)

    # Nothing fetched yet
    assert coordinator.should_update_energy()

    coordinator.update_time = time.time()
    assert not coordinator.should_update_energy()

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL_ENERGY - 1))
    assert not coordinator.should_update_energy()

    freezer.tick(timedelta(seconds=1))
    assert coordinator.should_update_energy()


async def test_command_holds_device_out_of_polling(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device changed from HA is not polled until the grace period ends."""
    held = MagicMock(cid="held", sub_device_no=None, update=AsyncMock())
    other = MagicMock(cid="other", sub_device_no=None, update=AsyncMock())
    manager = MagicMock()
    manager.devices.__iter__.side_effect = lambda: iter([held, other])
    manager.devices.outlets = []
    coordinator = VeSyncDataCoordinator(hass, config_entry, manager)

    coordinator.async_mark_command(held)
    await coordinator._async_update_data()
    held.update.assert_not_called()
    other.update.assert_called_once()

    freezer.tick(timedelta(seconds=COMMAND_GRACE_PERIOD))
    await coordinator._async_update_data()
    held.update.assert_called_once()
    assert other.update.call_count == 2


async def test_update_fails_only_when_every_device_fails(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Test a full cloud outage raises UpdateFailed but one failing device does not."""
    first = MagicMock(cid="first", sub_device_no=None, update=AsyncMock())
    second = MagicMock(cid="second", sub_device_no=None, update=AsyncMock())
    manager = MagicMock()
    manager.devices.__iter__.side_effect = lambda: iter([first, second])
    manager.devices.outlets = []
    coordinator = VeSyncDataCoordinator(hass, config_entry, manager)

    first.update.side_effect = VeSyncError("offline")
    await coordinator._async_update_data()

    second.update.side_effect = VeSyncError("offline")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
