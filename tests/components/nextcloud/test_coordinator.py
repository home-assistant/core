"""Tests for the Nextcloud coordinator."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from nextcloudmonitor import (
    NextcloudMonitor,
    NextcloudMonitorAuthorizationError,
    NextcloudMonitorConnectionError,
    NextcloudMonitorRequestError,
)

from homeassistant.components.nextcloud.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.nextcloud.coordinator import (
    NextcloudDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import mock_config_entry
from .const import NC_DATA, VALID_CONFIG

from tests.common import async_fire_time_changed


async def test_data_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a coordinator data updates."""
    entry = mock_config_entry(VALID_CONFIG)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nextcloud.NextcloudMonitor", spec=NextcloudMonitor
        ) as mock_nextcloud_monitor,
    ):
        mock_nextcloud_monitor.return_value.update = Mock(
            return_value=True,
            side_effect=[
                None,
                NextcloudMonitorAuthorizationError,
                NextcloudMonitorConnectionError,
                NextcloudMonitorRequestError,
                None,
            ],
        )
        mock_nextcloud_monitor.return_value.data = NC_DATA
        assert await hass.config_entries.async_setup(entry.entry_id)
        coordinator: NextcloudDataUpdateCoordinator = entry.runtime_data

        # Test successful setup and first data fetch
        await hass.async_block_till_done(wait_background_tasks=True)
        assert entry.state == ConfigEntryState.LOADED
        assert coordinator.last_update_success

        # Test unsuccessful data fetch due to NextcloudMonitorAuthorizationError
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert coordinator.last_update_success is False
        assert isinstance(coordinator.last_exception, UpdateFailed) is True

        # Test unsuccessful data fetch due to NextcloudMonitorConnectionError
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert coordinator.last_update_success is False
        assert isinstance(coordinator.last_exception, UpdateFailed) is True

        # Test unsuccessful data fetch due to NextcloudMonitorRequestError
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert coordinator.last_update_success is False
        assert isinstance(coordinator.last_exception, UpdateFailed) is True

        # Test successful data fetch
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert coordinator.last_update_success
