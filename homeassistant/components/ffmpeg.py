"""
Component that will help set the FFmpeg component.

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
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['ha-ffmpeg==1.9']

DOMAIN = 'ffmpeg'

_LOGGER = logging.getLogger(__name__)

SERVICE_START = 'start'
SERVICE_STOP = 'stop'
SERVICE_RESTART = 'restart'

SIGNAL_FFMPEG_START = 'ffmpeg.start'
SIGNAL_FFMPEG_STOP = 'ffmpeg.stop'
SIGNAL_FFMPEG_RESTART = 'ffmpeg.restart'

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


@callback
def async_start(hass, entity_id=None):
    """Start a FFmpeg process on entity."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_START, data))


@callback
def async_stop(hass, entity_id=None):
    """Stop a FFmpeg process on entity."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_STOP, data))


@callback
def async_restart(hass, entity_id=None):
    """Restart a FFmpeg process on entity."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_RESTART, data))


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the FFmpeg component."""
    conf = config.get(DOMAIN, {})

    manager = FFmpegManager(
        hass,
        conf.get(CONF_FFMPEG_BIN, DEFAULT_BINARY),
        conf.get(CONF_RUN_TEST, DEFAULT_RUN_TEST)
    )

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    # Register service
    @asyncio.coroutine
    def async_service_handle(service):
        """Handle service ffmpeg process."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        if service.service == SERVICE_START:
            async_dispatcher_send(hass, SIGNAL_FFMPEG_START, entity_ids)
        elif service.service == SERVICE_STOP:
            async_dispatcher_send(hass, SIGNAL_FFMPEG_STOP, entity_ids)
        else:
            async_dispatcher_send(hass, SIGNAL_FFMPEG_RESTART, entity_ids)

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

    @property
    def binary(self):
        """Return ffmpeg binary from config."""
        return self._bin

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
    """Interface object for FFmpeg."""

    def __init__(self, initial_state=True):
        """Initialize ffmpeg base object."""
        self.ffmpeg = None
        self.initial_state = initial_state

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register dispatcher & events.

        This method is a coroutine.
        """
        async_dispatcher_connect(
            self.hass, SIGNAL_FFMPEG_START, self._async_start_ffmpeg)
        async_dispatcher_connect(
            self.hass, SIGNAL_FFMPEG_STOP, self._async_stop_ffmpeg)
        async_dispatcher_connect(
            self.hass, SIGNAL_FFMPEG_RESTART, self._async_restart_ffmpeg)

        # register start/stop
        self._async_register_events()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.ffmpeg.is_running

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @asyncio.coroutine
    def _async_start_ffmpeg(self, entity_ids):
        """Start a FFmpeg process.

        This method is a coroutine.
        """
        raise NotImplementedError()

    @asyncio.coroutine
    def _async_stop_ffmpeg(self, entity_ids):
        """Stop a FFmpeg process.

        This method is a coroutine.
        """
        if entity_ids is None or self.entity_id in entity_ids:
            yield from self.ffmpeg.close()

    @asyncio.coroutine
    def _async_restart_ffmpeg(self, entity_ids):
        """Stop a FFmpeg process.

        This method is a coroutine.
        """
        if entity_ids is None or self.entity_id in entity_ids:
            yield from self._async_stop_ffmpeg(None)
            yield from self._async_start_ffmpeg(None)

    @callback
    def _async_register_events(self):
        """Register a FFmpeg process/device."""
        @asyncio.coroutine
        def async_shutdown_handle(event):
            """Stop FFmpeg process."""
            yield from self._async_stop_ffmpeg(None)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, async_shutdown_handle)

        # start on startup
        if not self.initial_state:
            return

        @asyncio.coroutine
        def async_start_handle(event):
            """Start FFmpeg process."""
            yield from self._async_start_ffmpeg(None)
            self.async_schedule_update_ha_state()

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_start_handle)
