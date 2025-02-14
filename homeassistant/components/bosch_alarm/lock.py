"""Support for Bosch Alarm Panel doors as locks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)


class PanelLockEntity(LockEntity):
    """A lock entity for a lock on a bosch alarm panel."""

    def __init__(self, id, panel_conn, door) -> None:
        """Set up a lock entity for a lock on a bosch alarm panel."""
        self._observer = door.status_observer
        self._panel = panel_conn.panel
        self._attr_unique_id = f"{panel_conn.unique_id}_door_{id}"
        self._attr_device_info = panel_conn.device_info()
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._door = door
        self._door_id = id

    @property
    def name(self) -> str:
        """Return the name of the door."""
        return self._door.name

    @property
    def is_locked(self) -> bool:
        """Return if the door is locked."""
        return self._door.is_locked()

    @property
    def available(self) -> bool:
        """Return if the door is available."""
        return self._door.is_open() or self._door.is_locked()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door."""
        await self._panel.door_relock(self._door_id)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self._panel.door_unlock(self._door_id)

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        self._observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._observer.detach(self.schedule_update_ha_state)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lock entities for each door."""

    panel_conn = config_entry.runtime_data
    panel = panel_conn.panel

    async_add_entities(
        PanelLockEntity(lock_id, panel_conn, door)
        for (lock_id, door) in panel.doors.items()
    )
