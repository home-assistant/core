"""Tests for the VeSync coordinator."""

from datetime import timedelta
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pyvesync import VeSync
from pyvesync.utils.errors import VeSyncError, VeSyncLoginError

from homeassistant.components.vesync.const import (
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_ENERGY,
)
from homeassistant.components.vesync.coordinator import (
    COMMAND_GRACE_PERIOD,
    VeSyncDataCoordinator,
)
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

    with patch.object(coordinator, "async_update_listeners") as listeners_mock:
        coordinator.async_mark_command(held)
    listeners_mock.assert_called_once()
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


async def test_update_does_not_fail_while_a_device_is_held(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Test a failing poll does not mark a held device unavailable."""
    held = MagicMock(cid="held", sub_device_no=None, update=AsyncMock())
    other = MagicMock(
        cid="other",
        sub_device_no=None,
        update=AsyncMock(side_effect=VeSyncError("offline")),
    )
    manager = MagicMock()
    manager.devices.__iter__.side_effect = lambda: iter([held, other])
    manager.devices.outlets = []
    coordinator = VeSyncDataCoordinator(hass, config_entry, manager)

    with patch.object(coordinator, "async_update_listeners"):
        coordinator.async_mark_command(held)
    await coordinator._async_update_data()

    held.update.assert_not_called()
    other.update.assert_called_once()


async def test_update_failed_on_vesync_error(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    outlet: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test VeSync errors are surfaced as update failures."""
    outlet.update = AsyncMock(side_effect=VeSyncError("API failure"))
    manager.devices.outlets.append(outlet)
    coordinator = VeSyncDataCoordinator(hass, config_entry, manager)
    coordinator.async_add_listener(lambda: None)

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

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

    # Device poll errors are only logged, so update_energy is what can raise
    outlet.update_energy = AsyncMock(side_effect=VeSyncLoginError("Login failed"))

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL_ENERGY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = list(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
