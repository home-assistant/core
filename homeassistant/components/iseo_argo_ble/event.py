"""ISEO Argo BLE access log event entity."""

from typing import Any, cast, override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IseoConfigEntry
from .const import DOMAIN, signal_access_log

PARALLEL_UPDATES = 0

EVENT_TYPE_OPENED = "opened"
EVENT_TYPE_ACCESS_DENIED = "access_denied"
EVENT_TYPE_FAULT = "fault"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IseoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the access log event entity from a config entry."""
    async_add_entities([IseoAccessLogEvent(entry)])


class IseoAccessLogEvent(EventEntity):
    """Reports what the lock recorded in its access log.

    The lock keeps its own log of who opened the door and whose credential was
    turned away. The entries are read when the lock entity sees the door open,
    and on demand through the `read_access_log` action; this entity reports the
    newest entry of each kind from every read.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "access_log"
    _attr_event_types = [
        EVENT_TYPE_OPENED,
        EVENT_TYPE_ACCESS_DENIED,
        EVENT_TYPE_FAULT,
    ]

    def __init__(self, entry: IseoConfigEntry) -> None:
        """Initialize the access log event entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_access_log"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, entry.unique_id))},
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Listen for entries read from the lock's access log."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_access_log(self._entry.entry_id),
                self._async_handle_entry,
            )
        )

    @callback
    def _async_handle_entry(self, event_type: str, attributes: dict[str, Any]) -> None:
        """Report one access log entry."""
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
