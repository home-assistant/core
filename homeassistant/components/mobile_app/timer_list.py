"""Timer list for mobile app devices."""

from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.components import notify
from homeassistant.components.timer_list import (
    InMemoryTimerListEntity,
    TimerListEvent,
    TimerListEventType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import device_action
from .helpers import device_info
from .util import supports_push

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list of a mobile app device that supports push."""
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    # A finished timer can only reach the device as a push notification.
    if not supports_push(hass, webhook_id):
        return

    async_add_entities([MobileAppTimerList(entry)])


class MobileAppTimerList(InMemoryTimerListEntity):
    """Timer list of a mobile app device."""

    _attr_has_entity_name = True
    _attr_translation_key = "timers"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._entry = entry
        self._attr_unique_id = f"{entry.data[ATTR_DEVICE_ID]}_timers"
        self._attr_device_info = device_info(entry.data)

    @override
    async def async_added_to_hass(self) -> None:
        """Send a push notification when a timer finishes."""
        await super().async_added_to_hass()
        self.async_on_remove(self.async_subscribe_updates(self._async_handle_event))

    @callback
    def _async_handle_event(self, event: TimerListEvent) -> None:
        """Notify the device of a finished timer."""
        if event.event_type != TimerListEventType.FINISHED:
            return

        item = event.item
        if item.name:
            message = f"{item.name} finished"
        else:
            duration = timedelta(seconds=round(item.total_duration.total_seconds()))
            message = f"{duration} timer finished"

        if TYPE_CHECKING:
            assert self.device_entry is not None
        self._entry.async_create_task(
            self.hass,
            device_action.async_call_action_from_config(
                self.hass,
                {
                    CONF_DEVICE_ID: self.device_entry.id,
                    notify.ATTR_MESSAGE: message,
                    notify.ATTR_DATA: {
                        "group": "timers",
                        # Android
                        "channel": "Timers",
                        "importance": "high",
                        "ttl": 0,
                        "priority": "high",
                        # iOS
                        "push": {
                            "interruption-level": "time-sensitive",
                        },
                    },
                },
                {},
                None,
            ),
            "mobile_app_timer_notification",
        )
