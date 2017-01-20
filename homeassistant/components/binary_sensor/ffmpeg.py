"""
Provides a binary sensor which is a collection of ffmpeg tools.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ffmpeg/
"""
import asyncio
import logging
from os import path

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DOMAIN)
from homeassistant.components.ffmpeg import (
    DATA_FFMPEG, CONF_INPUT, CONF_OUTPUT, CONF_EXTRA_ARGUMENTS)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, EVENT_HOMEASSISTANT_START, CONF_NAME,
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


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Create the binary sensor."""
    from haffmpeg import SensorNoise, SensorMotion

    # check source
    if not hass.data[DATA_FFMPEG].async_run_test(config.get(CONF_INPUT)):
        return

    # generate sensor object
    if config.get(CONF_TOOL) == FFMPEG_SENSOR_NOISE:
        entity = FFmpegNoise(SensorNoise, config)
    else:
        entity = FFmpegMotion(SensorMotion, config)

    @asyncio.coroutine
    def async_shutdown(event):
        """Stop ffmpeg."""
        yield from entity.async_shutdown_ffmpeg()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_shutdown())

    @asyncio.coroutine
    def async_start(event):
        """Start ffmpeg."""
        yield from entity.async_start_ffmpeg()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, async_start())

    # add to system
    yield from async_add_devies([entity])
    DEVICES.append(entity)

    # exists service?
    if hass.services.has_service(DOMAIN, SERVICE_RESTART):
        return

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    # register service
    @asyncio.coroutine
    def async_service_handle_restart(service):
        """Handle service binary_sensor.ffmpeg_restart."""
        entity_ids = service.data.get('entity_id')

        if entity_ids:
            _devices = [device for device in DEVICES
                        if device.entity_id in entity_ids]
        else:
            _devices = DEVICES

        for device in _devices:
            yield from device.async_shutdown_ffmpeg()
            yield from device.async_start_ffmpeg()

    hass.services.async_register(
        DOMAIN, SERVICE_RESTART, async_service_handle_restart,
        descriptions.get(SERVICE_RESTART), schema=SERVICE_RESTART_SCHEMA)


class FFmpegBinarySensor(BinarySensorDevice):
    """A binary sensor which use ffmpeg for noise detection."""

    def __init__(self, ffobj, config):
        """Constructor for binary sensor noise detection."""
        self._manager = hass.data[DATA_FFMPEG]
        self._state = False
        self._config = config
        self._name = config.get(CONF_NAME)
        self._ffmpeg = ffobj(
            self._manager.binary, hass.loop, self._async_callback)

    def _async_callback(self, state):
        """HA-FFmpeg callback for noise detection."""
        self._state = state
        self.hass.async_add_job(self.async_update_ha_state())

    def async_start_ffmpeg(self):
        """Start a FFmpeg instance.

        This method must be run in the event loop and returns a coroutine.
        """
        raise NotImplementedError()

    def async_shutdown_ffmpeg(self, event):
        """For STOP event to shutdown ffmpeg.

        This method must be run in the event loop and returns a coroutine.
        """
        return self._ffmpeg.close()

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

    def async_start_ffmpeg(self):
        """Start a FFmpeg instance.

        This method must be run in the event loop and returns a coroutine.
        """
        # init config
        self._ffmpeg.set_options(
            time_duration=self._config.get(CONF_DURATION),
            time_reset=self._config.get(CONF_RESET),
            peak=self._config.get(CONF_PEAK),
        )

        # run
        return self._ffmpeg.open_sensor(
            input_source=self._config.get(CONF_INPUT),
            output_dest=self._config.get(CONF_OUTPUT),
            extra_cmd=self._config.get(CONF_EXTRA_ARGUMENTS),
        )

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return "sound"


class FFmpegMotion(FFmpegBinarySensor):
    """A binary sensor which use ffmpeg for noise detection."""

    def async_start_ffmpeg(self):
        """Start a FFmpeg instance.

        This method must be run in the event loop and returns a coroutine.
        """
        # init config
        self._ffmpeg.set_options(
            time_reset=self._config.get(CONF_RESET),
            time_repeat=self._config.get(CONF_REPEAT_TIME),
            repeat=self._config.get(CONF_REPEAT),
            changes=self._config.get(CONF_CHANGES),
        )

        # run
        return self._ffmpeg.open_sensor(
            input_source=self._config.get(CONF_INPUT),
            extra_cmd=self._config.get(CONF_EXTRA_ARGUMENTS),
        )

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return "motion"
