"""Tests for the VeSync coordinator."""

from datetime import timedelta
import time
from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed
from pyvesync import VeSync
from pyvesync.utils.errors import VeSyncError, VeSyncLoginError

from homeassistant.components.vesync.const import (
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_ENERGY,
)
from homeassistant.components.vesync.coordinator import VeSyncDataCoordinator
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
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


async def test_update_failed_on_vesync_error(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test VeSync errors are surfaced as update failures."""
    manager.update_all_devices = AsyncMock(side_effect=VeSyncError("API failure"))
    coordinator = VeSyncDataCoordinator(hass, config_entry, manager)
    coordinator.async_add_listener(lambda: None)

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert str(coordinator.last_exception) == "The service is unavailable: API failure"


async def test_reauth_started_on_login_error(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    outlet: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a login error while polling starts a reauth flow."""
    manager.devices.outlets.append(outlet)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # update_all_devices logs device errors, so update_energy is what can raise
    outlet.update_energy = AsyncMock(side_effect=VeSyncLoginError("Login failed"))

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL_ENERGY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
