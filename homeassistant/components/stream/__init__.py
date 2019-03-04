"""
Provide functionality to stream video source.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/stream/
"""
import logging
import threading

import voluptuous as vol

from homeassistant.auth.util import generate_secret
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass

from .const import (
    DOMAIN, CONF_KEEPALIVE, ATTR_STREAMS, ATTR_ENDPOINTS)
from .worker import stream_worker
from .hls import async_setup_hls

REQUIREMENTS = ['av==6.1.2']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_KEEPALIVE, default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


@bind_hass
async def async_request_stream(hass, stream_source, fmt='hls',
                               options=None, preload=False):
    """Set up stream with token."""
    if DOMAIN not in hass.config.components:
        raise HomeAssistantError("Stream component is not set up.")

    if not stream_source:
        raise HomeAssistantError("Invalid stream source.")

    if options is None:
        options = {}

    keepalive = hass.data[DOMAIN][CONF_KEEPALIVE]
    try:
        streams = hass.data[DOMAIN][ATTR_STREAMS]
        stream = streams.get(stream_source)
        if not stream:
            stream = Stream(hass, stream_source,
                            options=options, keepalive=keepalive)
            streams[stream_source] = stream
        if not preload and not stream.access_token:
            stream.access_token = generate_secret()
            stream.start()
        return hass.data[DOMAIN][ATTR_ENDPOINTS][fmt].format(
            hass.config.api.base_url, stream.access_token)
    except Exception:
        raise HomeAssistantError('Unable to get stream')


@bind_hass
def get_stream(hass, stream_source):
    """Return available stream."""
    streams = hass.data[DOMAIN][ATTR_STREAMS]
    return streams.get(stream_source)


async def async_setup(hass, config):
    """Set up stream."""
    conf = config[DOMAIN] if config.get(DOMAIN, {}) else {}

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][CONF_KEEPALIVE] = conf.get(CONF_KEEPALIVE)
    hass.data[DOMAIN][ATTR_ENDPOINTS] = {}
    hass.data[DOMAIN][ATTR_STREAMS] = {}

    # Setup HLS
    hls_endpoint = await async_setup_hls(hass)
    hass.data[DOMAIN][ATTR_ENDPOINTS]['hls'] = hls_endpoint

    @callback
    def shutdown(event):
        """Stop all stream workers."""
        for stream in hass.data[DOMAIN][ATTR_STREAMS].values():
            stream.keepalive = False
            stream.stop()
        _LOGGER.info("Stopped stream workers.")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class Stream:
    """Represents a single stream."""

    # pylint: disable=dangerous-default-value
    def __init__(self, hass, source, options={}, keepalive=False):
        """Initialize a stream."""
        self.hass = hass
        self.source = source
        self.options = options
        self.keepalive = keepalive
        self.access_token = None
        self._container = None
        self._thread = None
        self._thread_quit = None
        self._outputs = {}

    @property
    def container(self):
        """Return container."""
        return self._container

    @property
    def outputs(self):
        """Return stream outputs."""
        return self._outputs

    def add_provider(self, provider):
        """Add provider output stream."""
        if not self._outputs.get(provider.format):
            self._outputs[provider.format] = provider
        return self._outputs[provider.format]

    def start(self):
        """Start a stream."""
        import av
        if self._thread is None or not self._thread.isAlive():
            self._container = av.open(self.source, options=self.options)
            self._thread_quit = threading.Event()
            self._thread = threading.Thread(
                name='stream_worker',
                target=stream_worker,
                args=(
                    self.hass, self, self._thread_quit))
            self._thread.start()
            _LOGGER.info("Started stream: %s", self.source)

    def stop(self):
        """Remove outputs and access token."""
        self._outputs = {}
        self.access_token = None

        if not self.keepalive:
            self._stop()

    def _stop(self):
        """Stop worker thread."""
        if self._thread is not None:
            self._thread_quit.set()
            self._thread.join()
            self._thread = None
            self._container = None
            _LOGGER.info("Stopped stream: %s", self.source)
