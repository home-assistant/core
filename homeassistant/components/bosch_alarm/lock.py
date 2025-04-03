"""Support for Bosch Alarm Panel doors as locks."""

from __future__ import annotations

from typing import Any

from bosch_alarm_mode2 import Panel

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lock entities for each door."""

    panel = config_entry.runtime_data

    async_add_entities(
        PanelLockEntity(
            panel,
            door_id,
            config_entry.unique_id or config_entry.entry_id,
        )
        for door_id in panel.doors
    )


PARALLEL_UPDATES = 0


class PanelLockEntity(LockEntity):
    """A lock entity for a door on a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, panel: Panel, door_id: int, unique_id: str) -> None:
        """Set up a lock entity for a door on a bosch alarm panel."""
        self.panel = panel
        self._door = panel.doors[door_id]
        self._attr_unique_id = f"{unique_id}_door_{door_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self._door.name,
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
            via_device=(
                DOMAIN,
                unique_id,
            ),
        )
        self._door_id = door_id

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
        await self.panel.door_relock(self._door_id)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self.panel.door_unlock(self._door_id)

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._door.status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._door.status_observer.detach(self.schedule_update_ha_state)
