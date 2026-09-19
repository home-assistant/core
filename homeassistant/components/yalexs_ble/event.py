"""yalexs ble event entity."""

from typing import Any, override

from yalexs_ble import ConnectionInfo, DoorActivity, LockActivity, LockInfo

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .const import ATTR_REMOTE_TYPE, ATTR_SLOT, ATTR_SOURCE, ATTR_TIMESTAMP
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData


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
    _attr_event_types = ["activity"]
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        data: YaleXSBLEData,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(data)
        self._attr_unique_id = f"{data.lock.address}operation"

    @callback
    def _async_activity_update(
        self,
        activity: DoorActivity | LockActivity,
        lock_info: LockInfo,
        connection_info: ConnectionInfo,
    ) -> None:
        """Handle activity update."""
        value, attributes = self._extract_values(activity)
        event_data = {
            "state": value,
            "attributes": attributes,
        }

        self._trigger_event("activity", event_data)
        self.async_write_ha_state()

    def _extract_values(
        self, activity: DoorActivity | LockActivity
    ) -> tuple[str | None, dict[str, Any]]:
        value: str | None = None
        attributes: dict[str, Any] = {}

        if isinstance(activity, DoorActivity):
            value = f"door_{activity.status.name.lower()}"
            attributes[ATTR_TIMESTAMP] = activity.timestamp
        elif isinstance(activity, LockActivity):
            value = f"lock_{activity.status.name.lower()}"
            attributes[ATTR_TIMESTAMP] = activity.timestamp
            attributes[ATTR_SOURCE] = activity.source.name.lower()
            if activity.remote_type is not None:
                attributes[ATTR_REMOTE_TYPE] = activity.remote_type.name.lower()
            if activity.slot is not None:
                attributes[ATTR_SLOT] = activity.slot

        return (value, attributes)

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks & perform initial updates."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_activity_callback(
                self._async_activity_update, request_update=True
            )
        )
