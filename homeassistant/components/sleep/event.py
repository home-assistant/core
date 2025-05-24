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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SleepAsAndroidConfigEntry
from .const import ATTR_EVENT, SLEEP_EVENT
from .entity import SleepAsAndroidEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class SleepAsAndroidEventEntityDescription(EventEntityDescription):
    """Sleep as Android sensor description."""

    event_types: list[str]


class SleepAsAndroidEvent(StrEnum):
    """Sleep as Android events."""

    ALARM_CLOCK = "alarm_clock"
    ANTI_SNORING = "antisnoring"
    APNEA_ALARM = "apnea_alarm"
    LULLABY = "lullaby"
    SLEEP_PHASE = "sleep_phase"
    SLEEP_TRACKING = "sleep_tracking"
    SOUND_EVENT = "sound_event"


EVENT_DESCRIPTIONS: tuple[SleepAsAndroidEventEntityDescription, ...] = (
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.SLEEP_TRACKING,
        translation_key=SleepAsAndroidEvent.SLEEP_TRACKING,
        device_class=EventDeviceClass.BUTTON,
        event_types=[
            "sleep_tracking_paused",
            "sleep_tracking_resumed",
            "sleep_tracking_started",
            "sleep_tracking_stopped",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.ALARM_CLOCK,
        translation_key=SleepAsAndroidEvent.ALARM_CLOCK,
        event_types=[
            "alarm_alert_dismiss",
            "alarm_alert_start",
            "alarm_rescheduled",
            "alarm_skip_next",
            "alarm_snooze_canceled",
            "alarm_snooze_clicked",
            "alarm_wake_up_check",
            "before_smart_period",
            "show_skip_next_alarm",
            "smart_period",
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
            "sound_event_baby",
            "sound_event_cough",
            "sound_event_laugh",
            "sound_event_snore",
            "sound_event_talk",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.LULLABY,
        translation_key=SleepAsAndroidEvent.LULLABY,
        event_types=[
            "lullaby_start",
            "lullaby_stop",
            "lullaby_volume_down",
        ],
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.ANTI_SNORING,
        translation_key=SleepAsAndroidEvent.ANTI_SNORING,
        event_types=[
            "antisnoring",
        ],
        entity_registry_enabled_default=False,
    ),
    SleepAsAndroidEventEntityDescription(
        key=SleepAsAndroidEvent.APNEA_ALARM,
        translation_key=SleepAsAndroidEvent.APNEA_ALARM,
        event_types=[
            "apnea_alarm",
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

    _attr_has_entity_name = True
    entity_description: SleepAsAndroidEventEntityDescription

    @callback
    def _async_handle_event(self, webhook_id: str, data: dict[str, str]) -> None:
        """Handle the Sleep as Android event."""

        if (
            webhook_id == self.webhook_id
            and data[ATTR_EVENT] in self.entity_description.event_types
        ):
            self._trigger_event(
                data[ATTR_EVENT],
                data,
            )
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register event callback."""

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SLEEP_EVENT, self._async_handle_event)
        )
