"""
Provide functionality to stream video source.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/stream/
"""
import logging
import threading

import voluptuous as vol

from homeassistant.auth.util import generate_secret
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass

from .const import (
    DOMAIN, CONF_KEEPALIVE, ATTR_STREAMS, ATTR_ENDPOINTS)
from .worker import stream_worker
from .hls import async_setup_hls

REQUIREMENTS = ['av==6.1.2', 'pillow==5.4.1']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_KEEPALIVE, default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=dangerous-default-value
@bind_hass
async def async_request_stream(hass, stream_source, options={}, preload=False):
    """Set up stream with token."""
    if DOMAIN not in hass.config.components:
        raise HomeAssistantError("Stream is not configured.")

    if not stream_source:
        raise HomeAssistantError("Invalid stream source.")

    keepalive = hass.data[DOMAIN][CONF_KEEPALIVE]
    try:
        streams = hass.data[DOMAIN][ATTR_STREAMS]
        stream = streams.get(stream_source)
        if not stream:
            stream = Stream(hass, stream_source,
                            options=options, keepalive=keepalive)
            hass.data[DOMAIN][ATTR_STREAMS][stream_source] = stream
        if not preload and not stream.access_token:
            stream.access_token = generate_secret()
            stream.start()
        return stream.access_token
    except Exception:
        raise HomeAssistantError('Unable to get stream')


@bind_hass
def get_stream(hass, stream_source):
    """Return available stream."""
    streams = hass.data[DOMAIN][ATTR_STREAMS]
    return streams.get(stream_source)


@bind_hass
def get_url(hass, fmt, stream_source=None, token=None):
    """Return stream access url."""
    if not token:
        stream = hass.data[DOMAIN][ATTR_STREAMS].get(stream_source)
        if stream:
            token = stream.access_token
    if token:
        return hass.data[DOMAIN][ATTR_ENDPOINTS][fmt].format(
            hass.config.api.base_url, token)
    return None


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
        self.__container = None
        self.__thread = None
        self.__thread_quit = None
        self.__outputs = {}

    @property
    def container(self):
        """Return container."""
        return self.__container

    @property
    def outputs(self):
        """Return stream outputs."""
        return self.__outputs

    def add_provider(self, provider):
        """Add provider output stream."""
        if not self.__outputs.get(provider.format):
            self.__outputs[provider.format] = provider
        return self.__outputs[provider.format]

    def start(self):
        """Start a stream."""
        import av
        if self.__thread is None or not self.__thread.isAlive():
            self.__container = av.open(self.source, options=self.options)
            self.__thread_quit = threading.Event()
            self.__thread = threading.Thread(
                name='stream_worker',
                target=stream_worker,
                args=(
                    self.hass, self, self.__thread_quit))
            self.__thread.start()

    def stop_stream(self):
        """Remove outputs and access token."""
        self.__outputs = {}
        self.access_token = None

        if not self.keepalive:
            self.stop()

    def stop(self):
        """Stop worker thread."""
        if self.__thread is not None:
            self.__thread_quit.set()
            self.__thread.join()
            self.__thread = None
            self.__container = None
