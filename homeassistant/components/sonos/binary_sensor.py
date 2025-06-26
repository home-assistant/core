"""Entity representing a Sonos power sensor."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .alarms import SonosAlarms
from .const import (
    ATTR_SCHEDULED_TODAY,
    SONOS_ALARMS_UPDATED,
    SONOS_CREATE_ALARM_SCHEDULED,
    SONOS_CREATE_BATTERY,
    SONOS_CREATE_MIC_SENSOR,
)
from .entity import SonosEntity
from .helpers import SonosConfigEntry, soco_error
from .speaker import SonosSpeaker

ATTR_BATTERY_POWER_SOURCE = "power_source"
ATTR_NEXT_ALARM_TRIGGER = "next_alarm_trigger"
ATTR_FOLLOWING_ALARM_TRIGGER = "following_alarm_trigger"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SonosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonos from a config entry."""

    @callback
    def _async_create_alarm_scheduled_entity(speaker: SonosSpeaker) -> None:
        _LOGGER.debug("Creating alarm scheduled binary_sensor on %s", speaker.zone_name)
        async_add_entities([SonosAlarmScheduledEntity(speaker, config_entry)])

    @callback
    def _async_create_battery_entity(speaker: SonosSpeaker) -> None:
        _LOGGER.debug("Creating battery binary_sensor on %s", speaker.zone_name)
        entity = SonosPowerEntity(speaker, config_entry)
        async_add_entities([entity])

    @callback
    def _async_create_mic_entity(speaker: SonosSpeaker) -> None:
        _LOGGER.debug("Creating microphone binary_sensor on %s", speaker.zone_name)
        async_add_entities([SonosMicrophoneSensorEntity(speaker, config_entry)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_ALARM_SCHEDULED, _async_create_alarm_scheduled_entity
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_BATTERY, _async_create_battery_entity
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SONOS_CREATE_MIC_SENSOR, _async_create_mic_entity
        )
    )


class SonosAlarmScheduledEntity(SonosEntity, BinarySensorEntity):
    """Representation of a Sonos Alarm Scheduled entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "alarm_scheduled"

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the alarm scheduled binary sensor."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-alarm-scheduled"
        self.household_id = speaker.household_id

    async def async_added_to_hass(self) -> None:
        """Handle binary sensor setup when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_ALARMS_UPDATED}-{self.household_id}",
                self.async_write_ha_state,
            )
        )

        async def async_write_state_daily(now: datetime.datetime) -> None:
            """Update state attributes each calendar day."""
            _LOGGER.debug("Daily update of alarm scheduled for %s", self.name)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_change(
                self.hass, async_write_state_daily, hour=0, minute=0, second=0
            )
        )

    async def _async_fallback_poll(self) -> None:
        """Call the central alarm polling method."""
        alarms: SonosAlarms = self.config_entry.runtime_data.alarms[self.household_id]
        assert alarms.async_poll
        await alarms.async_poll()

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        if self._next_alarm_trigger is None:
            return "mdi:alarm-off"
        if self._following_alarm_trigger is None:
            return "mdi:alarm"
        return "mdi:alarm-multiple"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self._next_alarm_trigger is not None

    @property
    def _is_today(self) -> bool:
        """Return whether the next alarm is scheduled for today."""
        if self._next_alarm_trigger is None:
            return False
        return self._next_alarm_trigger.date() == dt_util.now().date()

    @property
    def _next_alarm_trigger(self) -> datetime.datetime | None:
        """Return the next alarm time."""
        return self.speaker.alarms.get_next_alarm_datetime(zone_uid=self.soco.uid)

    @property
    def _following_alarm_trigger(self) -> datetime.datetime | None:
        """Return the following alarm after the current next one."""
        if self._next_alarm_trigger is None:
            return None
        return self.speaker.alarms.get_next_alarm_datetime(
            from_datetime=self._next_alarm_trigger + datetime.timedelta(minutes=1),
            zone_uid=self.soco.uid,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes of Sonos alarm scheduled binary sensor."""
        return {
            ATTR_SCHEDULED_TODAY: self._is_today,
            ATTR_NEXT_ALARM_TRIGGER: self._next_alarm_trigger,
            ATTR_FOLLOWING_ALARM_TRIGGER: self._following_alarm_trigger,
        }


class SonosPowerEntity(SonosEntity, BinarySensorEntity):
    """Representation of a Sonos power entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the power entity binary sensor."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-power"

    async def _async_fallback_poll(self) -> None:
        """Poll the device for the current state."""
        await self.speaker.async_poll_battery()

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.speaker.charging

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            ATTR_BATTERY_POWER_SOURCE: self.speaker.power_source,
        }

    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self.speaker.available and self.speaker.charging is not None


class SonosMicrophoneSensorEntity(SonosEntity, BinarySensorEntity):
    """Representation of a Sonos microphone sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "microphone"

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the microphone binary sensor entity."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-microphone"

    async def _async_fallback_poll(self) -> None:
        """Handle polling when subscription fails."""
        await self.hass.async_add_executor_job(self.poll_state)

    @soco_error()
    def poll_state(self) -> None:
        """Poll the current state of the microphone."""
        self.speaker.mic_enabled = self.soco.mic_enabled

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.speaker.mic_enabled
