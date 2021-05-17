"""Entity representing a Sonos battery level."""
from __future__ import annotations

import datetime
import logging

from pysonos.alarms import Alarm
from pysonos.exceptions import SoCoUPnPException

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.const import ATTR_TIME
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import SonosData
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

    async def _async_create_entity(speaker: SonosSpeaker) -> None:
        data_sonos = hass.data[DATA_SONOS]

        for alarm in speaker.available_alarms:
            # pylint: disable=protected-access
            if alarm._alarm_id not in data_sonos.alarms:
                # pylint: disable=protected-access
                _LOGGER.debug("Creating alarm with id %s", alarm._alarm_id)
                entity = SonosAlarmEntity(alarm, data_sonos, speaker)
                async_add_entities([entity])
                # pylint: disable=protected-access
                data_sonos.alarms.append(alarm._alarm_id)
                config_entry.async_on_unload(
                    async_dispatcher_connect(
                        hass, SONOS_ALARM_UPDATE, entity.async_update
                    )
                )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_ALARM, _async_create_entity)
    )


def get_speaker_from_uid(uid: str, data_sonos: SonosData) -> SonosSpeaker:
    """Get speaker from player uid."""
    for discovered_uid in data_sonos.discovered.keys():
        if discovered_uid == uid:
            return data_sonos.discovered[discovered_uid]

    raise RuntimeError("No configured Sonos speaker has been found to match the alarm.")


class SonosAlarmEntity(SonosEntity, SwitchEntity):
    """Representation of a Sonos Alarm entity."""

    def __init__(
        self, alarm: Alarm, data_sonos: SonosData, speaker: SonosSpeaker
    ) -> None:
        """Initialize the switch."""
        self.data_sonos = data_sonos
        self.alarm = alarm
        self.entity_id = ENTITY_ID_FORMAT.format(f"sonos_alarm_{self.alarm_id}")
        self._is_on = self.alarm.enabled

        self._attributes = {
            ATTR_ID: str(self.alarm_id),
            ATTR_TIME: str(self.alarm.start_time),
            ATTR_VOLUME: self.alarm.volume / 100,
            ATTR_DURATION: str(self.alarm.duration),
            ATTR_INCLUDE_LINKED_ZONES: self.alarm.include_linked_zones,
            ATTR_RECURRENCE: str(self.alarm.recurrence),
            ATTR_PLAY_MODE: str(self.alarm.play_mode),
            ATTR_SCHEDULED_TODAY: self._is_today,
        }

        super().__init__(speaker)

    @property
    def alarm_id(self):
        """Return the ID of the alarm."""
        # pylint: disable=protected-access
        return self.alarm._alarm_id

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

    async def async_remove_if_not_available(self):
        """Remove alarm entity if not available."""
        if self.alarm in self.speaker.available_alarms:
            return

        _LOGGER.debug("The alarm is removed from hass because it has been deleted")
        if self.alarm_id in self.hass.data[DATA_SONOS].alarms:
            self.hass.data[DATA_SONOS].alarms.remove(self.alarm_id)

        entity_registry = er.async_get(self.hass)
        if entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)

    async def async_update(self, now: datetime.datetime | None = None) -> None:
        """Poll the device for the current state."""
        await self.async_remove_if_not_available()
        await self.hass.async_add_executor_job(self.update_alarm)

    def _update_device(self):
        """Update the device, since this alarm moved to a different player."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        entity = entity_registry.async_get(self.entity_id)

        entry_id = entity.config_entry_id

        new_device = device_registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(SONOS_DOMAIN, self.soco.uid)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.speaker.mac_address)},
        )
        if not entity_registry.async_get(self.entity_id).device_id == new_device.id:
            _LOGGER.debug("The alarm is switching the sonos player")
            # pylint: disable=protected-access
            entity_registry._async_update_entity(
                self.entity_id, device_id=new_device.id
            )

    def update_alarm(self):
        """Update the state of the alarm."""
        _LOGGER.debug("Updating the state of the alarm")
        if self.speaker.soco.uid != self.alarm.zone.uid:
            self.speaker.available_alarms.remove(self.alarm)
            self.speaker = get_speaker_from_uid(self.alarm.zone.uid, self.data_sonos)
            self.speaker.available_alarms.add(self.alarm)
            self._update_device()

        self._is_on = self.alarm.enabled
        self._attributes[ATTR_ID] = str(self.alarm_id)
        self._attributes[ATTR_TIME] = str(self.alarm.start_time)
        self._attributes[ATTR_DURATION] = str(self.alarm.duration)
        self._attributes[ATTR_RECURRENCE] = str(self.alarm.recurrence)
        self._attributes[ATTR_VOLUME] = self.alarm.volume / 100
        self._attributes[ATTR_PLAY_MODE] = str(self.alarm.play_mode)
        self._attributes[ATTR_SCHEDULED_TODAY] = self._is_today
        self._attributes[ATTR_INCLUDE_LINKED_ZONES] = self.alarm.include_linked_zones

        self.schedule_update_ha_state()

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
        return self._is_on

    @property
    def device_state_attributes(self):
        """Return attributes of Sonos alarm switch."""
        return self._attributes

    async def async_turn_on(self, **kwargs) -> None:
        """Turn alarm switch on."""
        success = await self.async_handle_switch_on_off(turn_on=True)
        if success:
            self._is_on = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn alarm switch off."""
        success = await self.async_handle_switch_on_off(turn_on=False)
        if success:
            self._is_on = False

    async def async_handle_switch_on_off(self, turn_on: bool) -> bool:
        """Handle turn on/off of alarm switch."""
        try:
            _LOGGER.debug("Switching the state of the alarm")
            self.alarm.enabled = turn_on
            await self.hass.async_add_executor_job(self.alarm.save)
            return True
        except SoCoUPnPException as exc:
            _LOGGER.warning(
                "Home Assistant couldn't switch the alarm %s", exc, exc_info=True
            )
            return False
