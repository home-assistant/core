"""Timer list for ESPHome voice satellites."""

from functools import partial

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

from .entry_data import ESPHomeConfigEntry, RuntimeEntryData
from .enum_mapper import EsphomeEnumMapper

PARALLEL_UPDATES = 0

_TIMER_EVENT_TYPES: EsphomeEnumMapper[
    VoiceAssistantTimerEventType, TimerListEventType
] = EsphomeEnumMapper(
    {
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_STARTED: (
            TimerListEventType.STARTED
        ),
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED: (
            TimerListEventType.UPDATED
        ),
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED: (
            TimerListEventType.CANCELLED
        ),
        VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_FINISHED: (
            TimerListEventType.FINISHED
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list for a voice-capable ESPHome device."""
    entry_data = entry.runtime_data
    device_info = entry_data.device_info
    assert device_info is not None
    if not device_info.voice_assistant_feature_flags_compat(entry_data.api_version):
        return

    mac = device_info.mac_address
    entity = InMemoryTimerListEntity(
        name="Timers",
        unique_id=f"{mac}-timer_list",
        device_info=DeviceInfo(connections={(dr.CONNECTION_NETWORK_MAC, mac)}),
    )
    async_add_entities([entity])

    entry.async_on_unload(
        entity.async_subscribe_updates(partial(_async_forward_timer_event, entry_data))
    )


@callback
def _async_forward_timer_event(
    entry_data: RuntimeEntryData, event: TimerListEvent
) -> None:
    """Forward a timer event to the ESPHome device over its API connection."""
    if not entry_data.available:
        # Satellite disconnected, drop timer event
        return

    try:
        native_event_type = _TIMER_EVENT_TYPES.from_hass(event.event_type)
    except KeyError:
        # e.g. REMOVED, which ESPHome has no event for
        return

    item = event.item
    entry_data.client.send_voice_assistant_timer_event(
        native_event_type,
        item.timer_id,
        item.name,
        int(item.duration.total_seconds()),
        round(item.remaining_at(dt_util.utcnow()).total_seconds()),
        item.status == TimerStatus.ACTIVE,
    )
