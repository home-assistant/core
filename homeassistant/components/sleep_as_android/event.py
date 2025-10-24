"""Event platform for Sleep as Android integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SleepAsAndroidConfigEntry
from .const import ATTR_EVENT, MAP_EVENTS
from .entity import SleepAsAndroidEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class SleepAsAndroidEventEntityDescription(EventEntityDescription):
    """Sleep as Android sensor description."""

    event_types: list[str]


class SleepAsAndroidEvent(StrEnum):
    """Sleep as Android events."""

    ALARM_CLOCK = "alarm_clock"
    USER_NOTIFICATION = "user_notification"
    SMART_WAKEUP = "smart_wakeup"
    SLEEP_HEALTH = "sleep_health"
    LULLABY = "lullaby"
    SLEEP_PHASE = "sleep_phase"
    SLEEP_TRACKING = "sleep_tracking"
    SOUND_EVENT = "sound_event"
    JET_LAG_PREVENTION = "jet_lag_prevention"


EVENT_DESCRIPTIONS: tuple[SleepAsAndroidEventEntityDescription, ...] = (
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.SLEEP_TRACKING,
        translation_key=SleepAsAndroidEvent.SLEEP_TRACKING,
        device_class=EventDeviceClass.BUTTON,
        event_types=[
            "paused",
            "resumed",
            "started",
            "stopped",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.ALARM_CLOCK,
        translation_key=SleepAsAndroidEvent.ALARM_CLOCK,
        event_types=[
            "alert_dismiss",
            "alert_start",
            "rescheduled",
            "skip_next",
            "snooze_canceled",
            "snooze_clicked",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.SMART_WAKEUP,
        translation_key=SleepAsAndroidEvent.SMART_WAKEUP,
        event_types=[
            "before_smart_period",
            "smart_period",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.USER_NOTIFICATION,
        translation_key=SleepAsAndroidEvent.USER_NOTIFICATION,
        event_types=[
            "wake_up_check",
            "show_skip_next_alarm",
            "time_to_bed_alarm_alert",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.SLEEP_PHASE,
        translation_key=SleepAsAndroidEvent.SLEEP_PHASE,
        event_types=[
            "awake",
            "deep_sleep",
            "light_sleep",
            "not_awake",
            "rem",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.SOUND_EVENT,
        translation_key=SleepAsAndroidEvent.SOUND_EVENT,
        event_types=[
            "baby",
            "cough",
            "laugh",
            "snore",
            "talk",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.LULLABY,
        translation_key=SleepAsAndroidEvent.LULLABY,
        event_types=[
            "start",
            "stop",
            "volume_down",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.SLEEP_HEALTH,
        translation_key=SleepAsAndroidEvent.SLEEP_HEALTH,
        event_types=[
            "antisnoring",
            "apnea_alarm",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.JET_LAG_PREVENTION,
        translation_key=SleepAsAndroidEvent.JET_LAG_PREVENTION,
        event_types=[
            "jet_lag_start",
            "jet_lag_stop",
        ],
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SleepAsAndroidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""

    async_add_entities(
        SleepAsAndroidEventEntity(config_entry, description)
        for description in EVENT_DESCRIPTIONS
    )


class SleepAsAndroidEventEntity(SleepAsAndroidEntity, EventEntity):
    """An event entity."""

    entity_description: SleepAsAndroidEventEntityDescription

    @callback
    def _async_handle_event(self, webhook_id: str, data: dict[str, str]) -> None:
        """Handle the Sleep as Android event."""
        event = MAP_EVENTS.get(data[ATTR_EVENT], data[ATTR_EVENT])
        if (
            webhook_id == self.webhook_id
            and event in self.entity_description.event_types
        ):
            self._trigger_event(event)
            self.async_write_ha_state()
