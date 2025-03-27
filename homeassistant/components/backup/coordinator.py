"""Coordinator for Home Assistant Backup integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.backup import (
    async_subscribe_events,
    async_subscribe_platform_events,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER
from .manager import (
    BackupManager,
    BackupManagerState,
    BackupPlatformEvent,
    ManagerStateEvent,
)

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
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.unsubscribe: list[Callable[[], None]] = [
            async_subscribe_events(hass, self._on_event),
            async_subscribe_platform_events(hass, self._on_event),
        ]

        self.backup_manager = backup_manager

    @callback
    def _on_event(self, event: ManagerStateEvent | BackupPlatformEvent) -> None:
        """Handle new event."""
        LOGGER.debug("Received backup event: %s", event)
        self.config_entry.async_create_task(self.hass, self.async_refresh())

    async def _async_update_data(self) -> BackupCoordinatorData:
        """Update backup manager data."""
        return BackupCoordinatorData(
            self.backup_manager.state,
            self.backup_manager.config.data.last_completed_automatic_backup,
            self.backup_manager.config.data.schedule.next_automatic_backup,
        )

    @callback
    def async_unsubscribe(self) -> None:
        """Unsubscribe from events."""
        for unsub in self.unsubscribe:
            unsub()
