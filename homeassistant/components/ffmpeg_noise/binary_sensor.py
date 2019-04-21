"""
Provides a binary sensor which is a collection of ffmpeg tools.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ffmpeg_noise/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.components.ffmpeg_motion.binary_sensor import (
    FFmpegBinarySensor)
from homeassistant.components.ffmpeg import (
    DATA_FFMPEG, CONF_INPUT, CONF_OUTPUT, CONF_EXTRA_ARGUMENTS,
    CONF_INITIAL_STATE)
from homeassistant.const import CONF_NAME

DEPENDENCIES = ['ffmpeg']

_LOGGER = logging.getLogger(__name__)

CONF_PEAK = 'peak'
CONF_DURATION = 'duration'
CONF_RESET = 'reset'

DEFAULT_NAME = 'FFmpeg Noise'
DEFAULT_INIT_STATE = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_INITIAL_STATE, default=DEFAULT_INIT_STATE): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
    vol.Optional(CONF_OUTPUT): cv.string,
    vol.Optional(CONF_PEAK, default=-30): vol.Coerce(int),
    vol.Optional(CONF_DURATION, default=1):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_RESET, default=10):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the FFmpeg noise binary sensor."""
    manager = hass.data[DATA_FFMPEG]
    entity = FFmpegNoise(hass, manager, config)
    async_add_entities([entity])


class FFmpegNoise(FFmpegBinarySensor):
    """A binary sensor which use FFmpeg for noise detection."""

    def __init__(self, hass, manager, config):
        """Initialize FFmpeg noise binary sensor."""
        from haffmpeg.sensor import SensorNoise

        super().__init__(config)
        self.ffmpeg = SensorNoise(
            manager.binary, hass.loop, self._async_callback)

    async def _async_start_ffmpeg(self, entity_ids):
        """Start a FFmpeg instance.

        This method is a coroutine.
        """
        if entity_ids is not None and self.entity_id not in entity_ids:
            return

        self.ffmpeg.set_options(
            time_duration=self._config.get(CONF_DURATION),
            time_reset=self._config.get(CONF_RESET),
            peak=self._config.get(CONF_PEAK),
        )

        await self.ffmpeg.open_sensor(
            input_source=self._config.get(CONF_INPUT),
            output_dest=self._config.get(CONF_OUTPUT),
            extra_cmd=self._config.get(CONF_EXTRA_ARGUMENTS),
        )

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return 'sound'
