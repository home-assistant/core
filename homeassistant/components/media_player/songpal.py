"""
Support for Songpal-enabled (Sony) media devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.songpal/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_SET,
    SUPPORT_TURN_ON, MediaPlayerDevice, DOMAIN)
from homeassistant.const import (
    CONF_NAME, STATE_ON, STATE_OFF, ATTR_ENTITY_ID)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-songpal==0.0.7']

SUPPORT_SONGPAL = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP | \
                  SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF

_LOGGER = logging.getLogger(__name__)


PLATFORM = "songpal"

SET_SOUND_SETTING = "songpal_set_sound_setting"

PARAM_NAME = "name"
PARAM_VALUE = "value"

CONF_ENDPOINT = "endpoint"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_ENDPOINT): cv.string,
})

SET_SOUND_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(PARAM_NAME): cv.string,
    vol.Required(PARAM_VALUE): cv.string})


async def async_setup_platform(hass, config,
                               async_add_devices, discovery_info=None):
    """Set up the Songpal platform."""
    from songpal import SongpalException
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    if discovery_info is not None:
        name = discovery_info["name"]
        endpoint = discovery_info["properties"]["endpoint"]
        _LOGGER.debug("Got autodiscovered %s - endpoint: %s", name, endpoint)

        device = SongpalDevice(name, endpoint)
    else:
        name = config.get(CONF_NAME)
        endpoint = config.get(CONF_ENDPOINT)
        device = SongpalDevice(name, endpoint)

    try:
        await device.initialize()
    except SongpalException as ex:
        _LOGGER.error("Unable to get methods from songpal: %s", ex)
        raise PlatformNotReady

    hass.data[PLATFORM][endpoint] = device

    async_add_devices([device], True)

    async def async_service_handler(service):
        """Service handler."""
        entity_id = service.data.get("entity_id", None)
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}

        for device in hass.data[PLATFORM].values():
            if device.entity_id == entity_id or entity_id is None:
                _LOGGER.debug("Calling %s (entity: %s) with params %s",
                              service, entity_id, params)

                await device.async_set_sound_setting(params[PARAM_NAME],
                                                     params[PARAM_VALUE])

    hass.services.async_register(
        DOMAIN, SET_SOUND_SETTING, async_service_handler,
        schema=SET_SOUND_SCHEMA)


class SongpalDevice(MediaPlayerDevice):
    """Class representing a Songpal device."""

    def __init__(self, name, endpoint):
        """Init."""
        import songpal
        self._name = name
        self.endpoint = endpoint
        self.dev = songpal.Device(self.endpoint)
        self._sysinfo = None

        self._state = False
        self._available = False
        self._initialized = False

        self._volume_control = None
        self._volume_min = 0
        self._volume_max = 1
        self._volume = 0
        self._is_muted = False

        self._sources = []

    async def initialize(self):
        """Initialize the device."""
        await self.dev.get_supported_methods()
        self._sysinfo = await self.dev.get_system_info()

    @property
    def name(self):
        """Return name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._sysinfo.macAddr

    @property
    def available(self):
        """Return availability of the device."""
        return self._available

    async def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        await self.dev.set_sound_settings(name, value)

    async def async_update(self):
        """Fetch updates from the device."""
        from songpal import SongpalException
        try:
            volumes = await self.dev.get_volume_information()
            if not volumes:
                _LOGGER.error("Got no volume controls, bailing out")
                self._available = False
                return

            if len(volumes) > 1:
                _LOGGER.warning("Got %s volume controls, using the first one",
                                volumes)

            volume = volumes[0]
            _LOGGER.debug("Current volume: %s", volume)

            self._volume_max = volume.maxVolume
            self._volume_min = volume.minVolume
            self._volume = volume.volume
            self._volume_control = volume
            self._is_muted = self._volume_control.is_muted

            status = await self.dev.get_power()
            self._state = status.status
            _LOGGER.debug("Got state: %s", status)

            inputs = await self.dev.get_inputs()
            _LOGGER.debug("Got ins: %s", inputs)
            self._sources = inputs

            self._available = True
        except SongpalException as ex:
            # if we were available, print out the exception
            if self._available:
                _LOGGER.error("Got an exception: %s", ex)
            self._available = False

    async def async_select_source(self, source):
        """Select source."""
        for out in self._sources:
            if out.title == source:
                await out.activate()
                return

        _LOGGER.error("Unable to find output: %s", source)

    @property
    def source_list(self):
        """Return list of available sources."""
        return [x.title for x in self._sources]

    @property
    def state(self):
        """Return current state."""
        if self._state:
            return STATE_ON
        return STATE_OFF

    @property
    def source(self):
        """Return currently active source."""
        for out in self._sources:
            if out.active:
                return out.title

        return None

    @property
    def volume_level(self):
        """Return volume level."""
        volume = self._volume / self._volume_max
        return volume

    async def async_set_volume_level(self, volume):
        """Set volume level."""
        volume = int(volume * self._volume_max)
        _LOGGER.debug("Setting volume to %s", volume)
        return await self._volume_control.set_volume(volume)

    async def async_volume_up(self):
        """Set volume up."""
        return await self._volume_control.set_volume("+1")

    async def async_volume_down(self):
        """Set volume down."""
        return await self._volume_control.set_volume("-1")

    async def async_turn_on(self):
        """Turn the device on."""
        return await self.dev.set_power(True)

    async def async_turn_off(self):
        """Turn the device off."""
        return await self.dev.set_power(False)

    async def async_mute_volume(self, mute):
        """Mute or unmute the device."""
        _LOGGER.debug("Set mute: %s", mute)
        return await self._volume_control.set_mute(mute)

    @property
    def is_volume_muted(self):
        """Return whether the device is muted."""
        return self._is_muted

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_SONGPAL
