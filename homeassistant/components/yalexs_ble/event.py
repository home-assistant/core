"""yalexs ble event entity."""

from typing import Any, override

from yalexs_ble import DoorActivity, DoorStatus, LockActivity, LockStatus

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .const import ATTR_REMOTE_TYPE, ATTR_SLOT, ATTR_SOURCE, ATTR_TIMESTAMP
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData

DOOR_EVENT_TYPES: dict[DoorStatus, str] = {
    DoorStatus.CLOSED: "door_closed",
    DoorStatus.AJAR: "door_ajar",
    DoorStatus.OPENED: "door_opened",
}
LOCK_EVENT_TYPES: dict[LockStatus, str] = {
    LockStatus.UNLOCKING: "lock_unlocking",
    LockStatus.UNLOCKED: "lock_unlocked",
    LockStatus.LOCKING: "lock_locking",
    LockStatus.LOCKED: "lock_locked",
    LockStatus.JAMMED: "lock_jammed",
    LockStatus.SECUREMODE: "lock_securemode",
}
EVENT_TYPES = [*DOOR_EVENT_TYPES.values(), *LOCK_EVENT_TYPES.values()]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the yalexs ble event platform."""

    data = entry.runtime_data
    async_add_entities((YaleXSBLEEvent(data),))


class YaleXSBLEEvent(YALEXSBLEEntity, EventEntity):
    """Representation of a yalexs ble event entity."""

    _attr_translation_key = "operation"
    _attr_event_types = EVENT_TYPES
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        data: YaleXSBLEData,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(data)
        self._attr_unique_id = f"{data.lock.address}operation"

    @callback
    def _async_activity_update(self, activity: DoorActivity | LockActivity) -> None:
        """Handle a new activity record from the lock's log."""
        attributes: dict[str, Any] = {ATTR_TIMESTAMP: activity.timestamp}

        if isinstance(activity, DoorActivity):
            if (event_type := DOOR_EVENT_TYPES.get(activity.status)) is None:
                return
        elif isinstance(activity, LockActivity):
            if (event_type := LOCK_EVENT_TYPES.get(activity.status)) is None:
                return
            attributes[ATTR_SOURCE] = activity.source.name.lower()
            if activity.remote_type is not None:
                attributes[ATTR_REMOTE_TYPE] = activity.remote_type.name.lower()
            if activity.slot is not None:
                attributes[ATTR_SLOT] = activity.slot

        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks & perform initial updates."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_activity_callback(self._async_activity_update)
        )
