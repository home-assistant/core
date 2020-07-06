"""Provide functionality to stream video source."""
import logging
import secrets
import threading

import voluptuous as vol

from homeassistant.const import CONF_FILENAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
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
# Set log level to error for libav
logging.getLogger("libav").setLevel(logging.ERROR)


@bind_hass
def request_stream(hass, stream_source, *, fmt="hls", keepalive=False, options=None):
    """Set up stream with token."""
    if DOMAIN not in hass.config.components:
        raise HomeAssistantError("Stream integration is not set up.")

    if options is None:
        options = {}

    # For RTSP streams, prefer TCP
    if isinstance(stream_source, str) and stream_source[:7] == "rtsp://":
        options = {
            "rtsp_flags": "prefer_tcp",
            "stimeout": "5000000",
            **options,
        }

    try:
        streams = hass.data[DOMAIN][ATTR_STREAMS]
        stream = streams.get(stream_source)
        if not stream:
            stream = Stream(hass, stream_source, options=options, keepalive=keepalive)
            streams[stream_source] = stream
        else:
            # Update keepalive option on existing stream
            stream.keepalive = keepalive

        # Add provider
        stream.add_provider(fmt)

        if not stream.access_token:
            stream.access_token = secrets.token_hex()
            stream.start()
        return hass.data[DOMAIN][ATTR_ENDPOINTS][fmt].format(stream.access_token)
    except Exception:
        raise HomeAssistantError("Unable to get stream")


async def async_setup(hass, config):
    """Set up stream."""
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
        """Return stream outputs."""
        return self._outputs

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

        if self._thread is None or not self._thread.isAlive():
            self._thread_quit = threading.Event()
            self._thread = threading.Thread(
                name="stream_worker",
                target=stream_worker,
                args=(self.hass, self, self._thread_quit),
            )
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


async def async_handle_record_service(hass, call):
    """Handle save video service calls."""
    stream_source = call.data[CONF_STREAM_SOURCE]
    video_path = call.data[CONF_FILENAME]
    duration = call.data[CONF_DURATION]
    lookback = call.data[CONF_LOOKBACK]

    # Check for file access
    if not hass.config.is_allowed_path(video_path):
        raise HomeAssistantError(f"Can't write {video_path}, no access to path!")

    # Check for active stream
    streams = hass.data[DOMAIN][ATTR_STREAMS]
    stream = streams.get(stream_source)
    if not stream:
        stream = Stream(hass, stream_source)
        streams[stream_source] = stream

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
        num_segments = min(int(lookback // hls.target_duration), hls.num_segments)
        # Wait for latest segment, then add the lookback
        await hls.recv()
        recorder.prepend(list(hls.get_segment())[-num_segments:])
