"""ISEO Argo BLE access log event entity."""

from typing import Any, cast, override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PENDING_LOG_ENTRIES, IseoConfigEntry
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
        # Reading the log destroys it on the lock, so the lock entity only
        # reads while this entity is here to report to.
        self._entry.runtime_data.access_log_consumer = True
        self.async_on_remove(self._forget_consumer)

        # Anything drained after this entity last went away — an unload that
        # outran the wait for a long read — is reported now rather than lost.
        pending = self.hass.data.get(PENDING_LOG_ENTRIES, {}).pop(
            self._entry.entry_id, None
        )
        if pending:
            for event_type, attributes in pending:
                self._async_handle_entry(event_type, attributes)

    @callback
    def _forget_consumer(self) -> None:
        """Stop the lock reading a log this entity can no longer report."""
        self._entry.runtime_data.access_log_consumer = False

    @callback
    def _async_handle_entry(self, event_type: str, attributes: dict[str, Any]) -> None:
        """Report one access log entry."""
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
