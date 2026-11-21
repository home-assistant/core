"""Timer lists for ESPHome voice satellites."""

import math
from typing import TYPE_CHECKING, override

from aioesphomeapi import VoiceAssistantTimerEventType

from homeassistant.components.timer_list import (
    InMemoryTimerListEntity,
    TimerListEvent,
    TimerListEventType,
    TimerStatus,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import TIMER_LIST_KEY
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

PARALLEL_UPDATES = 0

# The firmware has a single event for every change to a running timer.
_TIMER_EVENT_TYPES: dict[TimerListEventType, VoiceAssistantTimerEventType] = {
    TimerListEventType.CREATED: VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_STARTED,
    TimerListEventType.PAUSED: VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED,
    TimerListEventType.UNPAUSED: (
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED
    ),
    TimerListEventType.TIME_CHANGED: (
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED
    ),
    TimerListEventType.CANCELLED: (
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED
    ),
    TimerListEventType.FINISHED: (
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_FINISHED
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list of an ESPHome voice satellite."""
    entry_data = entry.runtime_data
    device_info = entry_data.device_info
    if TYPE_CHECKING:
        assert device_info is not None
    async_add_entities([EsphomeTimerList(entry_data, device_info.mac_address)])


class EsphomeTimerList(InMemoryTimerListEntity):
    """Timers of an ESPHome voice satellite, which the device shows and rings.

    Timers are kept in Home Assistant, so they keep running while the device is
    disconnected; it misses the changes made in the meantime.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "timers"

    def __init__(self, entry_data: RuntimeEntryData, mac_address: str) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._entry_data = entry_data
        self._attr_unique_id = f"{mac_address}-{TIMER_LIST_KEY}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac_address)}
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Send timer changes to the device."""
        await super().async_added_to_hass()
        self.async_on_remove(self.async_subscribe_updates(self._async_send_event))

    @callback
    def _async_send_event(self, event: TimerListEvent) -> None:
        """Send a timer change to the device."""
        if not self._entry_data.available:
            return

        item = event.item
        if event.event_type == TimerListEventType.REMOVED:
            if item.status not in (TimerStatus.ACTIVE, TimerStatus.PAUSED):
                return
            # The device still has the timer, which it only drops when cancelled
            native_event_type = (
                VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED
            )
            seconds_left = 0
            is_active = False
        else:
            native_event_type = _TIMER_EVENT_TYPES[event.event_type]
            seconds_left = math.ceil(
                item.remaining_at(dt_util.utcnow()).total_seconds()
            )
            is_active = item.status == TimerStatus.ACTIVE

        self._entry_data.client.send_voice_assistant_timer_event(
            native_event_type,
            item.timer_id,
            item.name,
            round(item.total_duration.total_seconds()),
            seconds_left,
            is_active,
        )
