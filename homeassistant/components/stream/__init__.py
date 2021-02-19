"""Provide functionality to stream video source.

Components use create_stream with a stream source (e.g. an rtsp url) to create
a new Stream object. Stream manages:
  - Background work to fetch and decode a stream
  - Desired output formats
  - Home Assistant URLs for viewing a stream
  - Access tokens for URLs for viewing a stream

A Stream consists of a background worker and multiple output streams (e.g. hls
and recorder). The worker has a callback to retrieve the current active output
streams where it writes the decoded output packets.  The HLS stream has an
inactivity idle timeout that expires the access token. When all output streams
are inactive, the background worker is shut down. Alternatively, a Stream
can be configured with keepalive to always keep workers active.
"""
import logging
import secrets
import threading
import time
from typing import List

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_HLS_ENDPOINT,
    ATTR_STREAMS,
    DOMAIN,
    MAX_SEGMENTS,
    OUTPUT_IDLE_TIMEOUT,
    STREAM_RESTART_INCREMENT,
    STREAM_RESTART_RESET_TIME,
)
from .core import IdleTimer, StreamOutput
from .hls import HlsStreamOutput, async_setup_hls

_LOGGER = logging.getLogger(__name__)


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
    hass.data[DOMAIN][ATTR_STREAMS] = []

    # Setup HLS
    hass.data[DOMAIN][ATTR_HLS_ENDPOINT] = async_setup_hls(hass)

    # Setup Recorder
    async_setup_recorder(hass)

    @callback
    def shutdown(event):
        """Stop all stream workers."""
        for stream in hass.data[DOMAIN][ATTR_STREAMS]:
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
        self._hls = None
        self._hls_timer = None
        self._recorder = None
        self._fast_restart_once = False

        if self.options is None:
            self.options = {}

    def endpoint_url(self) -> str:
        """Start the stream and returns a url for the hls endpoint."""
        if not self._hls:
            raise ValueError("Stream is not configured for hls")
        if not self.access_token:
            self.access_token = secrets.token_hex()
        return self.hass.data[DOMAIN][ATTR_HLS_ENDPOINT].format(self.access_token)

    def outputs(self) -> List[StreamOutput]:
        """Return the active stream outputs."""
        return [output for output in [self._hls, self._recorder] if output]

    def hls_output(self) -> StreamOutput:
        """Return the hls output stream, creating if not already active."""
        if not self._hls:
            self._hls = HlsStreamOutput(self.hass)
            self._hls_timer = IdleTimer(self.hass, OUTPUT_IDLE_TIMEOUT, self._hls_idle)
            self._hls_timer.start()
        self._hls_timer.awake()
        return self._hls

    @callback
    def _hls_idle(self):
        """Reset access token and cleanup stream due to inactivity."""
        self.access_token = None
        if not self.keepalive:
            if self._hls:
                self._hls.cleanup()
                self._hls = None
            self._hls_timer = None
        self._check_idle()

    def _check_idle(self):
        """Check if all outputs are idle and shut down worker."""
        if self.keepalive or self.outputs():
            return
        self.stop()

    def start(self):
        """Start stream decode worker."""
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
            _LOGGER.info("Started stream: %s", self.source)

    def update_source(self, new_source):
        """Restart the stream with a new stream source."""
        _LOGGER.debug("Updating stream source %s", self.source)
        self.source = new_source
        self._fast_restart_once = True
        self._thread_quit.set()

    def _run_worker(self):
        """Handle consuming streams and restart keepalive streams."""
        # Keep import here so that we can import stream integration without installing reqs
        # pylint: disable=import-outside-toplevel
        from .worker import stream_worker

        wait_timeout = 0
        while not self._thread_quit.wait(timeout=wait_timeout):
            start_time = time.time()
            stream_worker(self.source, self.options, self.outputs, self._thread_quit)
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
        self.hass.loop.call_soon_threadsafe(self.stop)

    def stop(self):
        """Remove outputs and access token."""
        self.access_token = None
        if self._hls_timer:
            self._hls_timer.clear()
            self._hls_timer = None
        if self._hls:
            self._hls.cleanup()
            self._hls = None
        if self._recorder:
            self._recorder.save()
            self._recorder = None
        self._stop()

    def _stop(self):
        """Stop worker thread."""
        if self._thread is not None:
            self._thread_quit.set()
            self._thread.join()
            self._thread = None
            _LOGGER.info("Stopped stream: %s", self.source)

    async def async_record(self, video_path, duration=30, lookback=5):
        """Make a .mp4 recording from a provided stream."""

        # Keep import here so that we can import stream integration without installing reqs
        # pylint: disable=import-outside-toplevel
        from .recorder import RecorderOutput

        # Check for file access
        if not self.hass.config.is_allowed_path(video_path):
            raise HomeAssistantError(f"Can't write {video_path}, no access to path!")

        # Add recorder
        if self._recorder:
            raise HomeAssistantError(
                f"Stream already recording to {self._recorder.video_path}!"
            )
        self._recorder = RecorderOutput(self.hass)
        self._recorder.video_path = video_path
        self.start()

        # Take advantage of lookback
        if lookback > 0 and self._hls:
            num_segments = min(int(lookback // self._hls.target_duration), MAX_SEGMENTS)
            # Wait for latest segment, then add the lookback
            await self._hls.recv()
            self._recorder.prepend(list(self._hls.get_segment())[-num_segments:])

        @callback
        def save_recording():
            if self._recorder:
                self._recorder.save()
                self._recorder = None
            self._check_idle()

        IdleTimer(self.hass, duration, save_recording).start()
