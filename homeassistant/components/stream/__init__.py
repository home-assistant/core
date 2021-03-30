"""Provide functionality to stream video source.

Components use create_stream with a stream source (e.g. an rtsp url) to create
a new Stream object. Stream manages:
  - Background work to fetch and decode a stream
  - Desired output formats
  - Home Assistant URLs for viewing a stream
  - Access tokens for URLs for viewing a stream

A Stream consists of a background worker, and one or more output formats each
with their own idle timeout managed by the stream component. When an output
format is no longer in use, the stream component will expire it. When there
are no active output formats, the background worker is shut down and access
tokens are expired. Alternatively, a Stream can be configured with keepalive
to always keep workers active.
"""
import logging
import re
import secrets
import threading
import time
from types import MappingProxyType

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_ENDPOINTS,
    ATTR_STREAMS,
    DOMAIN,
    MAX_SEGMENTS,
    OUTPUT_IDLE_TIMEOUT,
    STREAM_RESTART_INCREMENT,
    STREAM_RESTART_RESET_TIME,
)
from .core import PROVIDERS, IdleTimer
from .hls import async_setup_hls

_LOGGER = logging.getLogger(__name__)

STREAM_SOURCE_RE = re.compile("//(.*):(.*)@")


def create_stream(hass, stream_source, options=None):
    """Create a stream with the specified identfier based on the source url.

    The stream_source is typically an rtsp url and options are passed into
    pyav / ffmpeg as options.
    """
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

    stream = Stream(hass, stream_source, options=options)
    hass.data[DOMAIN][ATTR_STREAMS].append(stream)
    return stream


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
    hass.data[DOMAIN][ATTR_STREAMS] = []

    # Setup HLS
    hls_endpoint = async_setup_hls(hass)
    hass.data[DOMAIN][ATTR_ENDPOINTS]["hls"] = hls_endpoint

    # Setup Recorder
    async_setup_recorder(hass)

    @callback
    def shutdown(event):
        """Stop all stream workers."""
        for stream in hass.data[DOMAIN][ATTR_STREAMS]:
            stream.keepalive = False
            stream.stop()
        _LOGGER.info("Stopped stream workers")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class Stream:
    """Represents a single stream."""

    def __init__(self, hass, source, options=None):
        """Initialize a stream."""
        self.hass = hass
        self.source = source
        self.options = options
        self.keepalive = False
        self.access_token = None
        self._thread = None
        self._thread_quit = threading.Event()
        self._outputs = {}
        self._fast_restart_once = False

        if self.options is None:
            self.options = {}

    def endpoint_url(self, fmt):
        """Start the stream and returns a url for the output format."""
        if fmt not in self._outputs:
            raise ValueError(f"Stream is not configured for format '{fmt}'")
        if not self.access_token:
            self.access_token = secrets.token_hex()
        return self.hass.data[DOMAIN][ATTR_ENDPOINTS][fmt].format(self.access_token)

    def outputs(self):
        """Return a copy of the stream outputs."""
        # A copy is returned so the caller can iterate through the outputs
        # without concern about self._outputs being modified from another thread.
        return MappingProxyType(self._outputs.copy())

    def add_provider(self, fmt, timeout=OUTPUT_IDLE_TIMEOUT):
        """Add provider output stream."""
        if not self._outputs.get(fmt):

            @callback
            def idle_callback():
                if (not self.keepalive or fmt == "recorder") and fmt in self._outputs:
                    self.remove_provider(self._outputs[fmt])
                self.check_idle()

            provider = PROVIDERS[fmt](
                self.hass, IdleTimer(self.hass, timeout, idle_callback)
            )
            self._outputs[fmt] = provider
        return self._outputs[fmt]

    def remove_provider(self, provider):
        """Remove provider output stream."""
        if provider.name in self._outputs:
            self._outputs[provider.name].cleanup()
            del self._outputs[provider.name]

        if not self._outputs:
            self.stop()

    def check_idle(self):
        """Reset access token if all providers are idle."""
        if all(p.idle for p in self._outputs.values()):
            self.access_token = None

    def start(self):
        """Start a stream."""
        if self._thread is None or not self._thread.is_alive():
            if self._thread is not None:
                # The thread must have crashed/exited. Join to clean up the
                # previous thread.
                self._thread.join(timeout=0)
            self._thread_quit.clear()
            self._thread = threading.Thread(
                name="stream_worker",
                target=self._run_worker,
            )
            self._thread.start()
            _LOGGER.info(
                "Started stream: %s", STREAM_SOURCE_RE.sub("//", str(self.source))
            )

    def update_source(self, new_source):
        """Restart the stream with a new stream source."""
        _LOGGER.debug("Updating stream source %s", new_source)
        self.source = new_source
        self._fast_restart_once = True
        self._thread_quit.set()

    def _run_worker(self):
        """Handle consuming streams and restart keepalive streams."""
        # Keep import here so that we can import stream integration without installing reqs
        # pylint: disable=import-outside-toplevel
        from .worker import SegmentBuffer, stream_worker

        segment_buffer = SegmentBuffer(self.outputs)
        wait_timeout = 0
        while not self._thread_quit.wait(timeout=wait_timeout):
            start_time = time.time()
            stream_worker(self.source, self.options, segment_buffer, self._thread_quit)
            segment_buffer.discontinuity()
            if not self.keepalive or self._thread_quit.is_set():
                if self._fast_restart_once:
                    # The stream source is updated, restart without any delay.
                    self._fast_restart_once = False
                    self._thread_quit.clear()
                    continue
                break
            # To avoid excessive restarts, wait before restarting
            # As the required recovery time may be different for different setups, start
            # with trying a short wait_timeout and increase it on each reconnection attempt.
            # Reset the wait_timeout after the worker has been up for several minutes
            if time.time() - start_time > STREAM_RESTART_RESET_TIME:
                wait_timeout = 0
            wait_timeout += STREAM_RESTART_INCREMENT
            _LOGGER.debug(
                "Restarting stream worker in %d seconds: %s",
                wait_timeout,
                self.source,
            )
        self._worker_finished()

    def _worker_finished(self):
        """Schedule cleanup of all outputs."""

        @callback
        def remove_outputs():
            for provider in self.outputs().values():
                self.remove_provider(provider)

        self.hass.loop.call_soon_threadsafe(remove_outputs)

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
            _LOGGER.info(
                "Stopped stream: %s", STREAM_SOURCE_RE.sub("//", str(self.source))
            )

    async def async_record(self, video_path, duration=30, lookback=5):
        """Make a .mp4 recording from a provided stream."""

        # Check for file access
        if not self.hass.config.is_allowed_path(video_path):
            raise HomeAssistantError(f"Can't write {video_path}, no access to path!")

        # Add recorder
        recorder = self.outputs().get("recorder")
        if recorder:
            raise HomeAssistantError(
                f"Stream already recording to {recorder.video_path}!"
            )
        recorder = self.add_provider("recorder", timeout=duration)
        recorder.video_path = video_path

        self.start()
        _LOGGER.debug("Started a stream recording of %s seconds", duration)

        # Take advantage of lookback
        hls = self.outputs().get("hls")
        if lookback > 0 and hls:
            num_segments = min(int(lookback // hls.target_duration), MAX_SEGMENTS)
            # Wait for latest segment, then add the lookback
            await hls.recv()
            recorder.prepend(list(hls.get_segment())[-num_segments:])
