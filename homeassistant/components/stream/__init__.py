"""Provide functionality to stream video source."""
import logging
import secrets
import threading
from types import MappingProxyType
from typing import Awaitable, Callable

import voluptuous as vol

from homeassistant.const import CONF_FILENAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass

from .const import (
    ATTR_ENDPOINTS,
    ATTR_STREAMS,
    CONF_DURATION,
    CONF_LOOKBACK,
    CONF_STREAM_SOURCE,
    DOMAIN,
    MAX_SEGMENTS,
    SERVICE_RECORD,
)
from .core import PROVIDERS
from .hls import async_setup_hls

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

STREAM_SERVICE_SCHEMA = vol.Schema({vol.Required(CONF_STREAM_SOURCE): cv.string})

SERVICE_RECORD_SCHEMA = STREAM_SERVICE_SCHEMA.extend(
    {
        vol.Required(CONF_FILENAME): cv.string,
        vol.Optional(CONF_DURATION, default=30): int,
        vol.Optional(CONF_LOOKBACK, default=0): int,
    }
)


class StreamSource:
    """Holds a Stream URL and other parameters.

    This class exists to support expiring stream URLs that need to be
    refreshed regularly.
    """

    def __init__(
        self,
        source: str,
        options: dict = None,
        keepalive: bool = False,
        cache_key: str = None,
    ):
        """Initialize StreamSource."""
        self._source = source
        self._keepalive = keepalive
        if options is None:
            options = {}
        # For RTSP streams, prefer TCP
        if isinstance(self.source, str) and self.source[:7] == "rtsp://":
            options = {
                "rtsp_flags": "prefer_tcp",
                "stimeout": "5000000",
                **options,
            }
        self._options = options
        if not cache_key:
            cache_key = source
        self._cache_key = cache_key

    @property
    def source(self) -> str:
        """Stream URL."""
        return self._source

    @property
    def options(self) -> dict:
        """Return ffpmeg options for the stream."""
        return self._options

    @property
    def keepalive(self) -> bool:
        """Determine if the stream should stay active, and retry on error."""
        return self._keepalive

    @property
    def cache_key(self) -> str:
        """Key to update an existing stream source."""
        return self._cache_key


@bind_hass
async def request_stream(
    hass: HomeAssistant,
    stream_source_cb: Callable[[], Awaitable[StreamSource]],
    *,
    fmt: str = "hls",
):
    """Set up stream with token."""
    if DOMAIN not in hass.config.components:
        raise HomeAssistantError("Stream integration is not set up.")

    # Currently this is invoked only once at the start of the worker, but needs to be invoked on expiration
    # to resolve issue #42793 to update expired urls.
    stream_source = await stream_source_cb()

    try:
        streams = hass.data[DOMAIN][ATTR_STREAMS]
        stream = streams.get(stream_source.cache_key)
        if not stream:
            stream = Stream(
                hass,
                stream_source.source,
                options=stream_source.options,
                keepalive=stream_source.keepalive,
            )
            streams[stream_source.cache_key] = stream
        else:
            # Update options on existing stream
            stream.source = stream_source.source
            stream.keepalive = stream_source.keepalive

        # Add provider
        stream.add_provider(fmt)

        if not stream.access_token:
            stream.access_token = secrets.token_hex()
            stream.start()
        return hass.data[DOMAIN][ATTR_ENDPOINTS][fmt].format(stream.access_token)
    except Exception as err:
        raise HomeAssistantError("Unable to get stream") from err


async def async_setup(hass, config):
    """Set up stream."""
    # Set log level to error for libav
    logging.getLogger("libav").setLevel(logging.ERROR)
    logging.getLogger("libav.mp4").setLevel(logging.ERROR)

    # Keep import here so that we can import stream integration without installing reqs
    # pylint: disable=import-outside-toplevel
    from .recorder import async_setup_recorder

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_ENDPOINTS] = {}
    hass.data[DOMAIN][ATTR_STREAMS] = {}

    # Setup HLS
    hls_endpoint = async_setup_hls(hass)
    hass.data[DOMAIN][ATTR_ENDPOINTS]["hls"] = hls_endpoint

    # Setup Recorder
    async_setup_recorder(hass)

    @callback
    def shutdown(event):
        """Stop all stream workers."""
        for stream in hass.data[DOMAIN][ATTR_STREAMS].values():
            stream.keepalive = False
            stream.stop()
        _LOGGER.info("Stopped stream workers")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    async def async_record(call):
        """Call record stream service handler."""
        await async_handle_record_service(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_RECORD, async_record, schema=SERVICE_RECORD_SCHEMA
    )

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
        """Return a copy of the stream outputs."""
        # A copy is returned so the caller can iterate through the outputs
        # without concern about self._outputs being modified from another thread.
        return MappingProxyType(self._outputs.copy())

    def add_provider(self, fmt):
        """Add provider output stream."""
        if not self._outputs.get(fmt):
            provider = PROVIDERS[fmt](self)
            self._outputs[fmt] = provider
        return self._outputs[fmt]

    def remove_provider(self, provider):
        """Remove provider output stream."""
        if provider.name in self._outputs:
            del self._outputs[provider.name]
            self.check_idle()

        if not self._outputs:
            self.stop()

    def check_idle(self):
        """Reset access token if all providers are idle."""
        if all([p.idle for p in self._outputs.values()]):
            self.access_token = None

    def start(self):
        """Start a stream."""
        # Keep import here so that we can import stream integration without installing reqs
        # pylint: disable=import-outside-toplevel
        from .worker import stream_worker

        if self._thread is None or not self._thread.is_alive():
            if self._thread is not None:
                # The thread must have crashed/exited. Join to clean up the
                # previous thread.
                self._thread.join(timeout=0)
            self._thread_quit = threading.Event()
            self._thread = threading.Thread(
                name="stream_worker",
                target=stream_worker,
                args=(self.hass, self, self._thread_quit),
            )
            self._thread.start()

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


async def async_handle_record_service(hass, call):
    """Handle save video service calls."""
    stream_source = StreamSource(call.data[CONF_STREAM_SOURCE])
    video_path = call.data[CONF_FILENAME]
    duration = call.data[CONF_DURATION]
    lookback = call.data[CONF_LOOKBACK]

    # Check for file access
    if not hass.config.is_allowed_path(video_path):
        raise HomeAssistantError(f"Can't write {video_path}, no access to path!")

    # Check for active stream
    streams = hass.data[DOMAIN][ATTR_STREAMS]
    stream = streams.get(stream_source.source)
    if not stream:
        stream = Stream(hass, stream_source)
        streams[stream_source.source] = stream

    # Add recorder
    recorder = stream.outputs.get("recorder")
    if recorder:
        raise HomeAssistantError(f"Stream already recording to {recorder.video_path}!")

    recorder = stream.add_provider("recorder")
    recorder.video_path = video_path
    recorder.timeout = duration

    stream.start()

    # Take advantage of lookback
    hls = stream.outputs.get("hls")
    if lookback > 0 and hls:
        num_segments = min(int(lookback // hls.target_duration), MAX_SEGMENTS)
        # Wait for latest segment, then add the lookback
        await hls.recv()
        recorder.prepend(list(hls.get_segment())[-num_segments:])
