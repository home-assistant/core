"""Provides a binary sensor which is a collection of ffmpeg tools."""
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.ffmpeg import (
    FFmpegBase, DATA_FFMPEG, CONF_INPUT, CONF_EXTRA_ARGUMENTS,
    CONF_INITIAL_STATE)
from homeassistant.const import CONF_NAME

_LOGGER = logging.getLogger(__name__)

CONF_RESET = 'reset'
CONF_CHANGES = 'changes'
CONF_REPEAT = 'repeat'
CONF_REPEAT_TIME = 'repeat_time'

DEFAULT_NAME = 'FFmpeg Motion'
DEFAULT_INIT_STATE = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_INITIAL_STATE, default=DEFAULT_INIT_STATE): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
    vol.Optional(CONF_RESET, default=10):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_CHANGES, default=10):
        vol.All(vol.Coerce(float), vol.Range(min=0, max=99)),
    vol.Inclusive(CONF_REPEAT, 'repeat'):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Inclusive(CONF_REPEAT_TIME, 'repeat'):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the FFmpeg binary motion sensor."""
    manager = hass.data[DATA_FFMPEG]
    entity = FFmpegMotion(hass, manager, config)
    async_add_entities([entity])


class FFmpegBinarySensor(FFmpegBase, BinarySensorDevice):
    """A binary sensor which use FFmpeg for noise detection."""

    def __init__(self, config):
        """Init for the binary sensor noise detection."""
        super().__init__(config.get(CONF_INITIAL_STATE))

        self._state = False
        self._config = config
        self._name = config.get(CONF_NAME)

    @callback
    def _async_callback(self, state):
        """HA-FFmpeg callback for noise detection."""
        self._state = state
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name


class FFmpegMotion(FFmpegBinarySensor):
    """A binary sensor which use FFmpeg for noise detection."""

    def __init__(self, hass, manager, config):
        """Initialize FFmpeg motion binary sensor."""
        from haffmpeg.sensor import SensorMotion

        super().__init__(config)
        self.ffmpeg = SensorMotion(
            manager.binary, hass.loop, self._async_callback)

    async def _async_start_ffmpeg(self, entity_ids):
        """Start a FFmpeg instance.

        This method is a coroutine.
        """
        if entity_ids is not None and self.entity_id not in entity_ids:
            return

        # init config
        self.ffmpeg.set_options(
            time_reset=self._config.get(CONF_RESET),
            time_repeat=self._config.get(CONF_REPEAT_TIME, 0),
            repeat=self._config.get(CONF_REPEAT, 0),
            changes=self._config.get(CONF_CHANGES),
        )

        # run
        await self.ffmpeg.open_sensor(
            input_source=self._config.get(CONF_INPUT),
            extra_cmd=self._config.get(CONF_EXTRA_ARGUMENTS),
        )

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return 'motion'
