"""Timer lists for ESPHome voice satellites."""

import logging
import math
from typing import TYPE_CHECKING, override

from aioesphomeapi import APIConnectionError, VoiceAssistantTimerEventType

from homeassistant.components.timer_list import (
    RestoreTimerListEntity,
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

_LOGGER = logging.getLogger(__name__)

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


class EsphomeTimerList(RestoreTimerListEntity):
    """Timers of an ESPHome voice satellite, which the device shows and rings.

    Timers are kept in Home Assistant, so they keep running while the device is
    disconnected, and across restarts of Home Assistant. Once it listens again,
    it is sent every running timer and told to drop the ones that ended in the
    meantime. It listens once the satellite has subscribed to its voice
    assistant: the firmware drops timer events from a connection that has not.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "timers"

    def __init__(self, entry_data: RuntimeEntryData, mac_address: str) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._entry_data = entry_data
        # Running timers the device was told about, to cancel there when they
        # end while it is disconnected
        self._device_timers: dict[str, str | None] = {}
        self._attr_unique_id = f"{mac_address}-{TIMER_LIST_KEY}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac_address)}
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Send timer changes to the device."""
        await super().async_added_to_hass()
        # The device was told about the timers running before a restart
        self._device_timers.update(self._restored_running)
        self.async_on_remove(self.async_subscribe_updates(self._async_send_event))
        self.async_on_remove(
            self._entry_data.async_subscribe_voice_assistant_subscribed(
                self._async_sync_device
            )
        )
        if self._entry_data.voice_assistant_subscribed:
            self._async_sync_device()

    @callback
    def _async_sync_device(self) -> None:
        """Send the device every running timer and cancel the ones that ended."""
        running = {
            timer.timer_id: timer
            for timer in self.timers
            if timer.status in (TimerStatus.ACTIVE, TimerStatus.PAUSED)
        }
        for timer_id, name in list(self._device_timers.items()):
            if timer_id not in running:
                # Ended while the device was away: drop it there without a
                # late ring
                self._async_send(
                    VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED,
                    timer_id,
                    name,
                    0,
                    0,
                    False,
                )
        now = dt_util.utcnow()
        for item in running.values():
            # The device may have missed changes or restarted and lost the
            # timer; an update adds a timer it does not know.
            self._async_send(
                VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED,
                item.timer_id,
                item.name,
                math.ceil(item.total_duration.total_seconds()),
                math.ceil(item.remaining_at(now).total_seconds()),
                item.status == TimerStatus.ACTIVE,
            )

    @callback
    def _async_send_event(self, event: TimerListEvent) -> None:
        """Send a timer change to the device."""
        if not self._entry_data.voice_assistant_subscribed:
            # Caught up with once it listens again
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

        self._async_send(
            native_event_type,
            item.timer_id,
            item.name,
            math.ceil(item.total_duration.total_seconds()),
            seconds_left,
            is_active,
        )

    @callback
    def _async_send(
        self,
        event_type: VoiceAssistantTimerEventType,
        timer_id: str,
        name: str | None,
        total_seconds: int,
        seconds_left: int,
        is_active: bool,
    ) -> None:
        """Send a timer event to the device and track what it shows."""
        try:
            self._entry_data.client.send_voice_assistant_timer_event(
                event_type, timer_id, name, total_seconds, seconds_left, is_active
            )
        except APIConnectionError as err:
            # The next reconnect brings the device up to date
            _LOGGER.debug("Could not send timer event for %s: %s", timer_id, err)
            return
        # Only once sent, so a timer is still cancelled on the next reconnect
        # if the connection drops while it is being cancelled
        if event_type in (
            VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED,
            VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_FINISHED,
        ):
            self._device_timers.pop(timer_id, None)
        else:
            self._device_timers[timer_id] = name
