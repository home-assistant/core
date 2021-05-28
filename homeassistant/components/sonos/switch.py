"""Entity representing a Sonos Alarm."""
from __future__ import annotations

import datetime
import logging

from pysonos.exceptions import SoCoUPnPException

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.const import ATTR_TIME
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DATA_SONOS,
    DOMAIN as SONOS_DOMAIN,
    SONOS_ALARM_UPDATE,
    SONOS_CREATE_ALARM,
)
from .entity import SonosEntity
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"
ATTR_ID = "alarm_id"
ATTR_PLAY_MODE = "play_mode"
ATTR_RECURRENCE = "recurrence"
ATTR_SCHEDULED_TODAY = "scheduled_today"
ATTR_VOLUME = "volume"
ATTR_INCLUDE_LINKED_ZONES = "include_linked_zones"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    configured_alarms = set()

    async def _async_create_entity(speaker: SonosSpeaker, new_alarms: set) -> None:
        for alarm_id in new_alarms:
            if alarm_id not in configured_alarms:
                _LOGGER.debug("Creating alarm with id %s", alarm_id)
                entity = SonosAlarmEntity(alarm_id, speaker)
                async_add_entities([entity])
                configured_alarms.add(alarm_id)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_ALARM, _async_create_entity)
    )


class SonosAlarmEntity(SonosEntity, SwitchEntity):
    """Representation of a Sonos Alarm entity."""

    def __init__(self, alarm_id: str, speaker: SonosSpeaker) -> None:
        """Initialize the switch."""
        super().__init__(speaker)

        self._alarm_id = alarm_id
        self.entity_id = ENTITY_ID_FORMAT.format(f"sonos_alarm_{self.alarm_id}")

    async def async_added_to_hass(self) -> None:
        """Handle switch setup when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SONOS_ALARM_UPDATE,
                self.async_update,
            )
        )

    @property
    def alarm(self):
        """Return the alarm instance."""
        return self.hass.data[DATA_SONOS].alarms[self.alarm_id]

    @property
    def alarm_id(self):
        """Return the ID of the alarm."""
        return self._alarm_id

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the switch."""
        return f"{SONOS_DOMAIN}-{self.alarm_id}"

    @property
    def icon(self):
        """Return icon of Sonos alarm switch."""
        return "mdi:alarm"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Sonos Alarm {} {} {}".format(
            self.speaker.zone_name,
            self.alarm.recurrence.title(),
            str(self.alarm.start_time)[0:5],
        )

    @callback
    def async_check_if_available(self):
        """Check if alarm exists and remove alarm entity if not available."""
        if self.alarm_id in self.hass.data[DATA_SONOS].alarms:
            return True

        _LOGGER.debug("%s has been deleted", self.entity_id)

        entity_registry = er.async_get(self.hass)
        if entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)

        return False

    async def async_update(self) -> None:
        """Poll the device for the current state."""
        if not self.async_check_if_available():
            return

        _LOGGER.debug("Updating alarm: %s", self.entity_id)
        if self.speaker.soco.uid != self.alarm.zone.uid:
            self.speaker = self.hass.data[DATA_SONOS].discovered.get(
                self.alarm.zone.uid
            )
            if self.speaker is None:
                raise RuntimeError(
                    "No configured Sonos speaker has been found to match the alarm."
                )

            self._async_update_device()

        self.async_write_ha_state()

    @callback
    def _async_update_device(self):
        """Update the device, since this alarm moved to a different player."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        entity = entity_registry.async_get(self.entity_id)

        if entity is None:
            raise RuntimeError("Alarm has been deleted by accident.")

        entry_id = entity.config_entry_id

        new_device = device_registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(SONOS_DOMAIN, self.soco.uid)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.speaker.mac_address)},
        )
        if not entity_registry.async_get(self.entity_id).device_id == new_device.id:
            _LOGGER.debug("%s is moving to %s", self.entity_id, new_device.name)
            # pylint: disable=protected-access
            entity_registry._async_update_entity(
                self.entity_id, device_id=new_device.id
            )

    @property
    def _is_today(self):
        recurrence = self.alarm.recurrence
        timestr = int(datetime.datetime.today().strftime("%w"))
        return (
            bool(recurrence[:2] == "ON" and str(timestr) in recurrence)
            or bool(recurrence == "DAILY")
            or bool(recurrence == "WEEKDAYS" and int(timestr) not in [0, 7])
            or bool(recurrence == "ONCE")
            or bool(recurrence == "WEEKDAYS" and int(timestr) not in [0, 7])
            or bool(recurrence == "WEEKENDS" and int(timestr) not in range(1, 7))
        )

    @property
    def is_on(self):
        """Return state of Sonos alarm switch."""
        return self.alarm.enabled

    @property
    def extra_state_attributes(self):
        """Return attributes of Sonos alarm switch."""
        return {
            ATTR_ID: str(self.alarm_id),
            ATTR_TIME: str(self.alarm.start_time),
            ATTR_DURATION: str(self.alarm.duration),
            ATTR_RECURRENCE: str(self.alarm.recurrence),
            ATTR_VOLUME: self.alarm.volume / 100,
            ATTR_PLAY_MODE: str(self.alarm.play_mode),
            ATTR_SCHEDULED_TODAY: self._is_today,
            ATTR_INCLUDE_LINKED_ZONES: self.alarm.include_linked_zones,
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn alarm switch on."""
        await self.async_handle_switch_on_off(turn_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn alarm switch off."""
        await self.async_handle_switch_on_off(turn_on=False)

    async def async_handle_switch_on_off(self, turn_on: bool) -> None:
        """Handle turn on/off of alarm switch."""
        try:
            _LOGGER.debug("Toggling the state of %s", self.entity_id)
            self.alarm.enabled = turn_on
            await self.hass.async_add_executor_job(self.alarm.save)
        except SoCoUPnPException as exc:
            _LOGGER.error("Could not update %s: %s", self.entity_id, exc, exc_info=True)
