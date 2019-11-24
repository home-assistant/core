"""Switch for Sonos alarms."""
from datetime import timedelta
import logging

import socket
import pysonos
from pysonos import alarms
from pysonos.exceptions import SoCoException

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from homeassistant.util import slugify

from . import (
    ATTR_INCLUDE_LINKED_ZONES,
    ATTR_TIME,
    ATTR_VOLUME,
    CONF_ADVERTISE_ADDR,
    CONF_INTERFACE_ADDR,
    CONF_HOSTS,
    DOMAIN as SONOS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
DISCOVERY_INTERVAL = 60

ATTR_DURATION = "duration"
ATTR_PLAY_MODE = "play_mode"
ATTR_RECURRENCE = "recurrence"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Sonos platform. Obsolete."""
    _LOGGER.error(
        "Loading Sonos alarms by switch platform config is no longer supported"
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    config = hass.data[SONOS_DOMAIN].get("media_player", {})
    _LOGGER.debug("Reached async_setup_entry of alarm, config=%s", config)

    advertise_addr = config.get(CONF_ADVERTISE_ADDR)
    if advertise_addr:
        pysonos.config.EVENT_ADVERTISE_IP = advertise_addr

    def _discovery(now=None):
        """Discover players from network or configuration."""
        hosts = config.get(CONF_HOSTS)
        _LOGGER.debug(hosts)
        alarm_list = []

        def _discovered_alarm(soco):
            """Handle a (re)discovered player."""
            try:
                _LOGGER.debug("Reached _discovered_player, soco=%s", soco)
                for one_alarm in alarms.get_alarms(soco):
                    if one_alarm.zone == soco and one_alarm not in alarm_list:
                        _LOGGER.debug("Adding new alarm")
                        alarm_list.append(one_alarm)
                        hass.add_job(
                            async_add_entities, [SonosAlarmSwitch(soco, one_alarm)],
                        )
            except SoCoException as ex:
                _LOGGER.debug("SoCoException, ex=%s", ex)

        if hosts:
            for host in hosts:
                try:
                    _LOGGER.debug("Testing %s", host)
                    player = pysonos.SoCo(socket.gethostbyname(host))
                    if player.is_visible:
                        # Make sure that the player is available
                        _ = player.volume

                        _discovered_alarm(player)
                except (OSError, SoCoException) as ex:
                    _LOGGER.debug("Exception %s", ex)
                    if now is None:
                        _LOGGER.warning("Failed to initialize '%s'", host)

            _LOGGER.debug("Tested all hosts")
            hass.helpers.event.call_later(DISCOVERY_INTERVAL, _discovery)
        else:
            _LOGGER.debug("Starting discovery thread")
            pysonos.discover_thread(
                _discovered_alarm,
                interval=DISCOVERY_INTERVAL,
                interface_addr=config.get(CONF_INTERFACE_ADDR),
            )

    _LOGGER.debug("Adding discovery job")
    hass.async_add_executor_job(_discovery)


class SonosAlarmSwitch(SwitchDevice):
    """Switch class for Sonos alarms."""

    def __init__(self, soco, alarm):
        """Init Sonos alarms switch."""
        self._icon = "mdi:alarm"
        self._soco = soco
        self._id = alarm._alarm_id
        self._is_available = True
        speaker_info = self._soco.get_speaker_info(True)
        self._unique_id = "{}-{}".format(soco.uid, self._id)
        self._name = "Sonos {} Alarm (id: {})".format(
            speaker_info["zone_name"], self._id
        )
        _entity_id = slugify("sonos_alarm_{}".format(self._id))
        self.entity_id = ENTITY_ID_FORMAT.format(_entity_id)
        self._model = speaker_info["model_name"]

        self.alarm = None
        for one_alarm in alarms.get_alarms(self._soco):
            # pylint: disable=protected-access
            if one_alarm._alarm_id == self._id:
                self.alarm = one_alarm

        self._is_on = self.alarm.enabled
        self._attributes = {
            ATTR_TIME: str(self.alarm.start_time),
            ATTR_VOLUME: self.alarm.volume / 100,
            ATTR_DURATION: str(self.alarm.duration),
            ATTR_INCLUDE_LINKED_ZONES: self.alarm.include_linked_zones,
            ATTR_RECURRENCE: str(self.alarm.recurrence),
            ATTR_PLAY_MODE: str(self.alarm.play_mode),
        }
        super().__init__()

    def update(self, now=None):
        """Retrieve latest state."""
        _LOGGER.debug("updating alarms")
        try:
            alarms.get_alarms(self._soco)
            self._is_on = self.alarm.enabled
            self._attributes[ATTR_TIME] = str(self.alarm.start_time)
            self._attributes[ATTR_DURATION] = str(self.alarm.duration)
            self._attributes[ATTR_RECURRENCE] = str(self.alarm.recurrence)
            self._attributes[ATTR_VOLUME] = self.alarm.volume / 100
            self._attributes[ATTR_PLAY_MODE] = str(self.alarm.play_mode)
            self._attributes[
                ATTR_INCLUDE_LINKED_ZONES
            ] = self.alarm.include_linked_zones
            self._is_available = True
            _LOGGER.debug("successfully updated alarms")
        except SoCoException as exc:
            _LOGGER.error(
                "Home Assistant couldnt update the state of the alarm %s",
                exc,
                exc_info=True,
            )
            self._is_available = False

    @property
    def name(self):
        """Return name of Sonos alarm switch."""
        return self._name

    @property
    def icon(self):
        """Return icon of Sonos alarm switch."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return attributes of Sonos alarm switch."""
        return self._attributes

    @property
    def is_on(self):
        """Return state of Sonos alarm switch."""
        return self._is_on

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(SONOS_DOMAIN, self._unique_id)},
            "name": self._name,
            "model": self._model.replace("Sonos ", ""),
            "manufacturer": "Sonos",
        }

    @property
    def available(self) -> bool:
        """Return unavailability of alarm switch."""
        return self._is_available

    def turn_on(self, **kwargs) -> None:
        """Turn alarm switch on."""
        if self.handle_switch_on_off(turn_on=True):
            self._is_on = True

    def turn_off(self, **kwargs) -> None:
        """Turn alarm switch off."""
        if self.handle_switch_on_off(turn_on=False):
            self._is_on = False

    def handle_switch_on_off(self, turn_on: bool) -> bool:
        """Handle turn on/off of alarm switch."""
        # pylint: disable=import-error
        try:
            self.alarm.enabled = turn_on
            self.alarm.save()
            self._is_available = True
            return True
        except SoCoException as exc:
            _LOGGER.error(
                "Home Assistant couldnt switch the alarm %s", exc, exc_info=True
            )
            self._is_available = False
            return False
