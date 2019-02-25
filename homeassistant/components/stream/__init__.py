"""
Provide functionality to stream video source.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/stream/
"""
import asyncio
import logging
import threading

from aiohttp import web
import voluptuous as vol

from homeassistant.auth.util import generate_secret
from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass
from homeassistant.setup import async_prepare_setup_platform

from .worker import stream_worker

REQUIREMENTS = ['av==6.1.2', 'pillow==5.4.1']

_LOGGER = logging.getLogger(__name__)

ATTR_OPTIONS = 'options'
ATTR_ENDPOINTS = 'endpoints'
ATTR_STREAMS = 'streams'

CONF_KEEPALIVE = 'keepalive'

OUTPUT_FORMATS = ['hls', 'mjpeg']

DEPENDENCIES = ['http']
DOMAIN = 'stream'

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
    except KeyError:
        _LOGGER.error("No stream found for %s", stream_source)

    raise HomeAssistantError('Unable to get stream')


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

    # Platforms here register the views
    async def async_setup_platform(p_type, p_config, disc_info=None):
        """Set up a stream platform."""
        platform = await async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)
        if platform is None:
            return

        try:
            # This should register all views required
            # by the different platforms
            endpoint = await platform.async_setup_platform(hass)
            hass.data[DOMAIN][ATTR_ENDPOINTS][p_type] = endpoint
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform: %s", p_type)
            return

    setup_tasks = [async_setup_platform(p_type, {})
                   for p_type in OUTPUT_FORMATS]

    if setup_tasks:
        await asyncio.wait(setup_tasks, loop=hass.loop)

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
        if self.__thread is None:
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


class StreamView(HomeAssistantView):
    """Base StreamView."""

    requires_auth = False
    platform = None

    def __init__(self):
        """Initialize a basic stream view."""
        self._unsub = None

    async def get(self, request, token, sequence=None):
        """Start a GET request."""
        hass = request.app['hass']

        stream = next((
            s for s in hass.data[DOMAIN][ATTR_STREAMS].values()
            if s.access_token == token), None)

        if not stream:
            raise web.HTTPUnauthorized()

        # Start worker if not already started
        stream.start()

        if self._unsub is not None:
            self._unsub()

        async def cleanup(_now):
            """Stop the stream."""
            stream.stop_stream()
            self._unsub = None

        self._unsub = async_call_later(hass, 300, cleanup)

        return await self.handle(request, stream, sequence)

    async def handle(self, request, stream, sequence):
        """Handle the stream request."""
        raise NotImplementedError()
