"""
Component that will help set the ffmpeg component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ffmpeg/
"""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.config import load_yaml_config_file
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DOMAIN = 'ffmpeg'
REQUIREMENTS = ["ha-ffmpeg==1.4"]

_LOGGER = logging.getLogger(__name__)

SERVICE_START = 'start'
SERVICE_STOP = 'stop'
SERVICE_RESTART = 'restart'

DATA_FFMPEG = 'ffmpeg'

CONF_INITIAL_STATE = 'initial_state'
CONF_INPUT = 'input'
CONF_FFMPEG_BIN = 'ffmpeg_bin'
CONF_EXTRA_ARGUMENTS = 'extra_arguments'
CONF_OUTPUT = 'output'
CONF_RUN_TEST = 'run_test'

DEFAULT_BINARY = 'ffmpeg'
DEFAULT_RUN_TEST = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_FFMPEG_BIN, default=DEFAULT_BINARY): cv.string,
        vol.Optional(CONF_RUN_TEST, default=DEFAULT_RUN_TEST): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_FFMPEG_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def start(hass, entity_id=None):
    """Start a ffmpeg process on entity."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_START, data)


def stop(hass, entity_id=None):
    """Stop a ffmpeg process on entity."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_STOP, data)


def restart(hass, entity_id=None):
    """Restart a ffmpeg process on entity."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_RESTART, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the FFmpeg component."""
    conf = config.get(DOMAIN, {})

    manager = FFmpegManager(
        hass,
        conf.get(CONF_FFMPEG_BIN, DEFAULT_BINARY),
        conf.get(CONF_RUN_TEST, DEFAULT_RUN_TEST)
    )

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    # register service
    @asyncio.coroutine
    def async_service_handle(service):
        """Handle service ffmpeg process."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        if entity_ids:
            devices = [device for device in manager.entities
                       if device.entity_id in entity_ids]
        else:
            devices = manager.entities

        tasks = []
        for device in devices:
            if service.service == SERVICE_START:
                tasks.append(device.async_start_ffmpeg())
            elif service.service == SERVICE_STOP:
                tasks.append(device.async_stop_ffmpeg())
            else:
                tasks.append(device.async_restart_ffmpeg())

        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

        tasks.clear()
        for device in devices:
            tasks.append(device.async_update_ha_state())

        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_START, async_service_handle,
        descriptions[DOMAIN].get(SERVICE_START), schema=SERVICE_FFMPEG_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_STOP, async_service_handle,
        descriptions[DOMAIN].get(SERVICE_STOP), schema=SERVICE_FFMPEG_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_RESTART, async_service_handle,
        descriptions[DOMAIN].get(SERVICE_RESTART),
        schema=SERVICE_FFMPEG_SCHEMA)

    hass.data[DATA_FFMPEG] = manager
    return True


class FFmpegManager(object):
    """Helper for ha-ffmpeg."""

    def __init__(self, hass, ffmpeg_bin, run_test):
        """Initialize helper."""
        self.hass = hass
        self._cache = {}
        self._bin = ffmpeg_bin
        self._run_test = run_test
        self._entities = []

    @property
    def binary(self):
        """Return ffmpeg binary from config."""
        return self._bin

    @property
    def entities(self):
        """Return ffmpeg entities for services."""
        return self._entities

    @callback
    def async_register_device(self, device):
        """Register a ffmpeg process/device."""
        self._entities.append(device)

        @asyncio.coroutine
        def async_shutdown(event):
            """Stop ffmpeg process."""
            yield from device.async_stop_ffmpeg()

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, async_shutdown)

        # start on startup
        if device.initial_state:
            @asyncio.coroutine
            def async_start(event):
                """Start ffmpeg process."""
                yield from device.async_start_ffmpeg()
                yield from device.async_update_ha_state()

            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, async_start)

    @asyncio.coroutine
    def async_run_test(self, input_source):
        """Run test on this input. TRUE is deactivate or run correct.

        This method must be run in the event loop.
        """
        from haffmpeg import Test

        if self._run_test:
            # if in cache
            if input_source in self._cache:
                return self._cache[input_source]

            # run test
            ffmpeg_test = Test(self.binary, loop=self.hass.loop)
            success = yield from ffmpeg_test.run_test(input_source)
            if not success:
                _LOGGER.error("FFmpeg '%s' test fails!", input_source)
                self._cache[input_source] = False
                return False
            self._cache[input_source] = True
        return True


class FFmpegBase(Entity):
    """Interface object for ffmpeg."""

    def __init__(self, initial_state=True):
        """Initialize ffmpeg base object."""
        self.ffmpeg = None
        self.initial_state = initial_state

    @property
    def available(self):
        """Return True if entity is available."""
        return self.ffmpeg.is_running

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    def async_start_ffmpeg(self):
        """Start a ffmpeg process.

        This method must be run in the event loop and returns a coroutine.
        """
        raise NotImplementedError()

    def async_stop_ffmpeg(self):
        """Stop a ffmpeg process.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.ffmpeg.close()

    @asyncio.coroutine
    def async_restart_ffmpeg(self):
        """Stop a ffmpeg process."""
        yield from self.async_stop_ffmpeg()
        yield from self.async_start_ffmpeg()
