"""Coordinator for Home Assistant Backup integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .manager import (
    BackupManager,
    BackupManagerState,
    BackupPlatformEvent,
    ManagerStateEvent,
)

_LOGGER = logging.getLogger(__name__)

type BackupConfigEntry = ConfigEntry[BackupDataUpdateCoordinator]


@dataclass
class BackupCoordinatorData:
    """Class to hold backup data."""

    backup_manager_state: BackupManagerState
    last_successful_automatic_backup: datetime | None
    next_scheduled_automatic_backup: datetime | None


class BackupDataUpdateCoordinator(DataUpdateCoordinator[BackupCoordinatorData]):
    """Class to retrieve backup status."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        backup_manager: BackupManager,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )
        backup_manager.async_subscribe_events(self._on_event)
        backup_manager.async_subscribe_platform_events(self._on_event)
        self.backup_manager = backup_manager

    def _on_event(self, event: ManagerStateEvent | BackupPlatformEvent) -> None:
        """Handle new event."""
        _LOGGER.debug("Received backup event: %s", event)
        self.hass.async_create_task(self.async_refresh())

    async def _async_update_data(self) -> BackupCoordinatorData:
        """Update backup manager data."""
        backups = await self.backup_manager.async_get_backups()
        newest_backup_date: datetime | None = None
        for backup in backups[0].values():
            if (backup_date := dt_util.parse_datetime(backup.date)) is None:
                continue
            if newest_backup_date is None or newest_backup_date < backup_date:
                newest_backup_date = backup_date

        next_scheduled_automatic_backup = (
            self.backup_manager.config.data.schedule.next_automatic_backup
        )

        return BackupCoordinatorData(
            backup_manager_state=self.backup_manager.state,
            last_successful_automatic_backup=newest_backup_date,
            next_scheduled_automatic_backup=next_scheduled_automatic_backup,
        )
