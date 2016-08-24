"""
Provides a binary sensor which is a collection of ffmpeg tools.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ffmpeg/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (BinarySensorDevice,
                                                    PLATFORM_SCHEMA)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, CONF_NAME

REQUIREMENTS = ["ha-ffmpeg==0.7"]

MAP_FFMPEG_BIN = [
    'noise'
]

CONF_TOOL = 'tool'
CONF_INPUT = 'input'
CONF_FFMPEG_BIN = 'ffmpeg_bin'
CONF_EXTRA_ARGUMENTS = 'extra_arguments'
CONF_OUTPUT = 'output'
CONF_PEAK = 'peak'
CONF_DURATION = 'duration'
CONF_RESET = 'reset'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOOL): vol.In(MAP_FFMPEG_BIN),
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_NAME, default="FFmpeg"): cv.string,
    vol.Optional(CONF_FFMPEG_BIN, default="ffmpeg"): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
    vol.Optional(CONF_OUTPUT): cv.string,
    vol.Optional(CONF_PEAK, default=-30): vol.Coerce(int),
    vol.Optional(CONF_DURATION, default=1):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_RESET, default=2):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the binary sensor."""
    if config.get(CONF_TOOL) == "noise":
        entity = FFmpegNoise(config)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, entity.shutdown_ffmpeg)
    add_entities([entity])


class FFmpegNoise(BinarySensorDevice):
    """A binary sensor which use ffmpeg for noise detection."""

    def __init__(self, config):
        """Constructor for binary sensor noise detection."""
        from haffmpeg import SensorNoise

        self._state = False
        self._name = config.get(CONF_NAME)
        self._ffmpeg = SensorNoise(config.get(CONF_FFMPEG_BIN), self._callback)

        # init config
        self._ffmpeg.set_options(
            time_duration=config.get(CONF_DURATION),
            time_reset=config.get(CONF_RESET),
            peak=config.get(CONF_PEAK),
        )

        # run
        self._ffmpeg.open_sensor(
            input_source=config.get(CONF_INPUT),
            output_dest=config.get(CONF_OUTPUT),
            extra_cmd=config.get(CONF_EXTRA_ARGUMENTS),
        )

    def _callback(self, state):
        """HA-FFmpeg callback for noise detection."""
        self._state = state
        self.update_ha_state()

    def shutdown_ffmpeg(self, event):
        """For STOP event to shutdown ffmpeg."""
        self._ffmpeg.close()

    @property
    def is_on(self):
        """True if the binary sensor is on."""
        return self._state

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return "sound"

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name
