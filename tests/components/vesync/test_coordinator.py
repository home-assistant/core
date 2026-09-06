"""Tests for the VeSync coordinator."""

from datetime import timedelta
import time

from freezegun.api import FrozenDateTimeFactory
from pyvesync import VeSync

from homeassistant.components.vesync.const import UPDATE_INTERVAL_ENERGY
from homeassistant.components.vesync.coordinator import VeSyncDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


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
