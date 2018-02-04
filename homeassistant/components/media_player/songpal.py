"""
Support for Songpal-enabled (Sony) media devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.songpal/
"""
import logging
import asyncio

import voluptuous as vol
from typing import List  # pylint: disable=F401

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_SET,
    SUPPORT_TURN_ON, MediaPlayerDevice, DOMAIN)
from homeassistant.const import (
    CONF_NAME, STATE_ON, STATE_OFF, ATTR_ENTITY_ID)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-songpal==0.0.6']

SUPPORT_SONGPAL = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP | \
                  SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF

_LOGGER = logging.getLogger(__name__)


SET_SOUND_SETTING = "songpal_set_sound_setting"
PARAM_NAME = "name"
PARAM_VALUE = "value"

CONF_ENDPOINT = "endpoint"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Required(CONF_ENDPOINT): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Songpal platform."""
    devices = []  # type: List[SongpalDevice]
    if discovery_info is not None:
        _LOGGER.debug("Got autodiscovered device: %s" % discovery_info)
        devices.append(SongpalDevice(discovery_info["name"],
                       discovery_info["properties"]["endpoint"]))
    else:
        songpal = SongpalDevice(config.get(CONF_NAME),
                                config.get(CONF_ENDPOINT))
        devices.append(songpal)

    async_add_devices(devices, True)

    @asyncio.coroutine
    def async_service_handler(service):
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_id = service.data.get("entity_id", None)
        _LOGGER.debug("Calling %s (entity: %s) with params %s",
                      service, entity_id, params)

        for device in devices:
            if entity_id is None or device.entity_id == entity_id:
                yield from device.async_set_sound_setting(params[PARAM_NAME],
                                                          params[PARAM_VALUE])

    schema = vol.Schema({vol.Required(PARAM_NAME): cv.string,
                         vol.Required(PARAM_VALUE): cv.string})
    hass.services.async_register(
        DOMAIN, SET_SOUND_SETTING, async_service_handler,
        schema=schema)


class SongpalDevice(MediaPlayerDevice):
    """Class representing a Songpal device."""
    def __init__(self, name, endpoint):
        """Init."""
        import songpal
        self._name = name
        self.endpoint = endpoint
        self._dev = songpal.Protocol(self.endpoint)
        self._sysinfo = None  # type: songpal.Sysinfo

        self._state = False
        self._available = False
        self._initialized = False

        self._volume_min = 0
        self._volume_max = 1
        self._volume = 0
        self._is_muted = False

        self._sources = []

    @property
    def name(self):
        """Return name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._sysinfo.macAddr

    @property
    def available(self):
        """Return availability of the device."""
        return self._available

    @property
    def dev(self):
        """Property for accessing the device handle."""
        return self._dev

    @asyncio.coroutine
    def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        res = yield from self.dev.set_sound_settings(name, value)

        return res

    @asyncio.coroutine
    def async_update(self):
        """Fetch updates from the device."""
        from songpal import SongpalException
        if not self._initialized:
            try:
                yield from self._dev.get_supported_methods()
                self._sysinfo = yield from self.dev.get_system_info()
                self._initialized = True
            except SongpalException as ex:
                _LOGGER.error("Unable to get methods from songpal: %s", ex)
                raise PlatformNotReady

        try:
            volumes = yield from self.dev.get_volume_information()
            if len(volumes) == 0:
                _LOGGER.error("Got no volume controls, bailing out")
                return
            if len(volumes) > 1:
                _LOGGER.warning("Got %s volume controls, using the first one",
                                volumes)
                return

            vol = volumes.pop()
            _LOGGER.debug("Current volume: %s", vol)
            self._volume_max = vol.maxVolume
            self._volume_min = vol.minVolume
            self._volume = vol.volume
            self._volume_control = vol
            self._is_muted = self._volume_control.is_muted

            status = yield from self.dev.get_power()
            self._state = status.status
            _LOGGER.debug("Got state: %s" % status)

            inputs = yield from self.dev.get_inputs()
            _LOGGER.debug("Got ins: %s" % inputs)
            self._sources = inputs

            self._available = True
        except SongpalException as ex:
            # if we were available, print out the exception
            if self._available:
                _LOGGER.error("Got an exception %s", ex, exc_info=True)
            self._available = False

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select source."""
        for out in self._sources:
            if out.title == source:
                yield from out.activate()
                return

        _LOGGER.error("Unable to find output: %s" % source)

    @property
    def source_list(self):
        """Return list of available sources."""
        return [x.title for x in self._sources]

    @property
    def state(self):
        """Return current state."""
        if self._state:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def source(self):
        """Return currently active source."""
        for out in self._sources:
            if out.active:
                return out.title

        _LOGGER.error("Unable to find active output!")

    @property
    def volume_level(self):
        """Return volume level."""
        volume = self._volume / self._volume_max
        _LOGGER.debug("Current volume: %s" % volume)
        return volume

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set volume level."""
        vol = int(volume * self._volume_max)
        _LOGGER.debug("Setting volume to %s" % vol)
        return self._volume_control.set_volume(vol)

    @asyncio.coroutine
    def async_volume_up(self):
        """Set volume up."""
        return self._volume_control.set_volume("+1")

    @asyncio.coroutine
    def async_volume_down(self):
        """Set volume down."""
        return self._volume_control.set_volume("-1")

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn the device on."""
        return self.dev.set_power(True)

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn the device off."""
        return self.dev.set_power(False)

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Mute or unmute the device."""
        _LOGGER.debug("Set mute: %s" % mute)
        return self._volume_control.set_mute(mute)

    @property
    def is_volume_muted(self):
        """Return whether the device is muted."""
        return self._is_muted

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_SONGPAL
