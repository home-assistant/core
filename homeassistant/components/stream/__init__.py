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
from homeassistant.loader import bind_hass

from .const import DOMAIN, ATTR_STREAMS, ATTR_ENDPOINTS
from .core import PROVIDERS
from .worker import stream_worker
from .hls import async_setup_hls

REQUIREMENTS = ['av==6.1.2']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)

# Set log level to error for libav
logging.getLogger('libav').setLevel(logging.ERROR)


@bind_hass
def request_stream(hass, stream_source, *, fmt='hls',
                   keepalive=False, options=None):
    """Set up stream with token."""
    if DOMAIN not in hass.config.components:
        raise HomeAssistantError("Stream component is not set up.")

    if options is None:
        options = {}

    # For RTSP streams, prefer TCP
    if isinstance(stream_source, str) \
            and stream_source[:7] == 'rtsp://' and not options:
        options['rtsp_flags'] = 'prefer_tcp'

    try:
        streams = hass.data[DOMAIN][ATTR_STREAMS]
        stream = streams.get(stream_source)
        if not stream:
            stream = Stream(hass, stream_source,
                            options=options, keepalive=keepalive)
            streams[stream_source] = stream
        else:
            # Update keepalive option on existing stream
            stream.keepalive = keepalive

        # Add provider
        stream.add_provider(fmt)

        if not stream.access_token:
            stream.access_token = generate_secret()
            stream.start()
        return hass.data[DOMAIN][ATTR_ENDPOINTS][fmt].format(
            stream.access_token)
    except Exception:
        raise HomeAssistantError('Unable to get stream')


async def async_setup(hass, config):
    """Set up stream."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_ENDPOINTS] = {}
    hass.data[DOMAIN][ATTR_STREAMS] = {}

    # Setup HLS
    hls_endpoint = async_setup_hls(hass)
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

    def __init__(self, hass, source, options=None, keepalive=False):
        """Initialize a stream."""
        self.hass = hass
        self.source = source
        self.options = options
        self.keepalive = keepalive
        self.access_token = None
        self._thread = None
        self._thread_quit = None
        self._outputs = {}

        if self.options is None:
            self.options = {}

    @property
    def outputs(self):
        """Return stream outputs."""
        return self._outputs

    def add_provider(self, fmt):
        """Add provider output stream."""
        provider = PROVIDERS[fmt](self)
        if not self._outputs.get(provider.format):
            self._outputs[provider.format] = provider
        return self._outputs[provider.format]

    def remove_provider(self, provider):
        """Remove provider output stream."""
        if provider.format in self._outputs:
            del self._outputs[provider.format]
            self.check_idle()

        if not self._outputs:
            self.stop()

    def check_idle(self):
        """Reset access token if all providers are idle."""
        if all([p.idle for p in self._outputs.values()]):
            self.access_token = None

    def start(self):
        """Start a stream."""
        if self._thread is None or not self._thread.isAlive():
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
            _LOGGER.info("Stopped stream: %s", self.source)
