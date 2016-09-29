"""
Provides a binary sensor which is a collection of ffmpeg tools.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ffmpeg/
"""
import logging
from os import path

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DOMAIN)
from homeassistant.components.ffmpeg import (
    get_binary, run_test, CONF_INPUT, CONF_OUTPUT, CONF_EXTRA_ARGUMENTS)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, CONF_NAME,
                                 ATTR_ENTITY_ID)

DEPENDENCIES = ['ffmpeg']

_LOGGER = logging.getLogger(__name__)

SERVICE_RESTART = 'ffmpeg_restart'

FFMPEG_SENSOR_NOISE = 'noise'
FFMPEG_SENSOR_MOTION = 'motion'

MAP_FFMPEG_BIN = [
    FFMPEG_SENSOR_NOISE,
    FFMPEG_SENSOR_MOTION
]

CONF_TOOL = 'tool'
CONF_PEAK = 'peak'
CONF_DURATION = 'duration'
CONF_RESET = 'reset'
CONF_CHANGES = 'changes'
CONF_REPEAT = 'repeat'
CONF_REPEAT_TIME = 'repeat_time'

DEFAULT_NAME = 'FFmpeg'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOOL): vol.In(MAP_FFMPEG_BIN),
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
    vol.Optional(CONF_OUTPUT): cv.string,
    vol.Optional(CONF_PEAK, default=-30): vol.Coerce(int),
    vol.Optional(CONF_DURATION, default=1):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_RESET, default=10):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_CHANGES, default=10):
        vol.All(vol.Coerce(float), vol.Range(min=0, max=99)),
    vol.Optional(CONF_REPEAT, default=0):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional(CONF_REPEAT_TIME, default=0):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
})

SERVICE_RESTART_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def restart(hass, entity_id=None):
    """Restart a ffmpeg process on entity."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_RESTART, data)


# list of all ffmpeg sensors
DEVICES = []


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the binary sensor."""
    from haffmpeg import SensorNoise, SensorMotion

    # check source
    if not run_test(config.get(CONF_INPUT)):
        return

    # generate sensor object
    if config.get(CONF_TOOL) == FFMPEG_SENSOR_NOISE:
        entity = FFmpegNoise(SensorNoise, config)
    else:
        entity = FFmpegMotion(SensorMotion, config)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, entity.shutdown_ffmpeg)

    # add to system
    add_entities([entity])
    DEVICES.append(entity)

    # exists service?
    if hass.services.has_service(DOMAIN, SERVICE_RESTART):
        return

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    # register service
    def _service_handle_restart(service):
        """Handle service binary_sensor.ffmpeg_restart."""
        entity_ids = service.data.get('entity_id')

        if entity_ids:
            _devices = [device for device in DEVICES
                        if device.entity_id in entity_ids]
        else:
            _devices = DEVICES

        for device in _devices:
            device.restart_ffmpeg()

    hass.services.register(DOMAIN, SERVICE_RESTART,
                           _service_handle_restart,
                           descriptions.get(SERVICE_RESTART),
                           schema=SERVICE_RESTART_SCHEMA)


class FFmpegBinarySensor(BinarySensorDevice):
    """A binary sensor which use ffmpeg for noise detection."""

    def __init__(self, ffobj, config):
        """Constructor for binary sensor noise detection."""
        self._state = False
        self._config = config
        self._name = config.get(CONF_NAME)
        self._ffmpeg = ffobj(get_binary(), self._callback)

        self._start_ffmpeg(config)

    def _callback(self, state):
        """HA-FFmpeg callback for noise detection."""
        self._state = state
        self.update_ha_state()

    def _start_ffmpeg(self, config):
        """Start a FFmpeg instance."""
        raise NotImplementedError

    def shutdown_ffmpeg(self, event):
        """For STOP event to shutdown ffmpeg."""
        self._ffmpeg.close()

    def restart_ffmpeg(self):
        """Restart ffmpeg with new config."""
        self._ffmpeg.close()
        self._start_ffmpeg(self._config)

    @property
    def is_on(self):
        """True if the binary sensor is on."""
        return self._state

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._ffmpeg.is_running


class FFmpegNoise(FFmpegBinarySensor):
    """A binary sensor which use ffmpeg for noise detection."""

    def _start_ffmpeg(self, config):
        """Start a FFmpeg instance."""
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

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return "sound"


class FFmpegMotion(FFmpegBinarySensor):
    """A binary sensor which use ffmpeg for noise detection."""

    def _start_ffmpeg(self, config):
        """Start a FFmpeg instance."""
        # init config
        self._ffmpeg.set_options(
            time_reset=config.get(CONF_RESET),
            time_repeat=config.get(CONF_REPEAT_TIME),
            repeat=config.get(CONF_REPEAT),
            changes=config.get(CONF_CHANGES),
        )

        # run
        self._ffmpeg.open_sensor(
            input_source=config.get(CONF_INPUT),
            extra_cmd=config.get(CONF_EXTRA_ARGUMENTS),
        )

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return "motion"
