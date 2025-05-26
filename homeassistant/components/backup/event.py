"""Event platform for Home Assistant Backup integration."""

from __future__ import annotations

from typing import Final

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BackupConfigEntry, BackupDataUpdateCoordinator
from .entity import BackupManagerBaseEntity
from .manager import CreateBackupEvent, CreateBackupState

ATTR_BACKUP_STAGE: Final[str] = "backup_stage"
ATTR_FAILED_REASON: Final[str] = "failed_reason"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BackupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Event set up for backup config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities([AutomaticBackupEvent(coordinator)])


class AutomaticBackupEvent(BackupManagerBaseEntity, EventEntity):
    """Representation of an automatic backup event."""

    _attr_event_types = [s.value for s in CreateBackupState]
    _unrecorded_attributes = frozenset({ATTR_FAILED_REASON, ATTR_BACKUP_STAGE})
    coordinator: BackupDataUpdateCoordinator

    def __init__(self, coordinator: BackupDataUpdateCoordinator) -> None:
        """Initialize the automatic backup event."""
        super().__init__(coordinator)
        self._attr_unique_id = "automatic_backup_event"
        self._attr_translation_key = "automatic_backup_event"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            not (data := self.coordinator.data)
            or (event := data.last_event) is None
            or not isinstance(event, CreateBackupEvent)
        ):
            return

        self._trigger_event(
            event.state,
            {
                ATTR_BACKUP_STAGE: event.stage,
                ATTR_FAILED_REASON: event.reason,
            },
        )
        self.async_write_ha_state()
