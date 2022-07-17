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
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import copy
import logging
import re
import secrets
import threading
import time
from types import MappingProxyType
from typing import Any, Final, cast

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENDPOINTS,
    ATTR_SETTINGS,
    ATTR_STREAMS,
    CONF_EXTRA_PART_WAIT_TIME,
    CONF_LL_HLS,
    CONF_PART_DURATION,
    CONF_RTSP_TRANSPORT,
    CONF_SEGMENT_DURATION,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
    DOMAIN,
    FORMAT_CONTENT_TYPE,
    HLS_PROVIDER,
    MAX_SEGMENTS,
    OUTPUT_FORMATS,
    OUTPUT_IDLE_TIMEOUT,
    RECORDER_PROVIDER,
    RTSP_TRANSPORTS,
    SEGMENT_DURATION_ADJUSTER,
    SOURCE_TIMEOUT,
    STREAM_RESTART_INCREMENT,
    STREAM_RESTART_RESET_TIME,
)
from .core import (
    PROVIDERS,
    STREAM_SETTINGS_NON_LL_HLS,
    IdleTimer,
    KeyFrameConverter,
    StreamOutput,
    StreamSettings,
)
from .diagnostics import Diagnostics
from .hls import HlsStreamOutput, async_setup_hls

__all__ = [
    "ATTR_SETTINGS",
    "CONF_EXTRA_PART_WAIT_TIME",
    "CONF_RTSP_TRANSPORT",
    "CONF_USE_WALLCLOCK_AS_TIMESTAMPS",
    "DOMAIN",
    "FORMAT_CONTENT_TYPE",
    "HLS_PROVIDER",
    "OUTPUT_FORMATS",
    "RTSP_TRANSPORTS",
    "SOURCE_TIMEOUT",
    "Stream",
    "create_stream",
]

_LOGGER = logging.getLogger(__name__)

STREAM_SOURCE_REDACT_PATTERN = [
    (re.compile(r"//.*:.*@"), "//****:****@"),
    (re.compile(r"\?auth=.*"), "?auth=****"),
]


def redact_credentials(data: str) -> str:
    """Redact credentials from string data."""
    for (pattern, repl) in STREAM_SOURCE_REDACT_PATTERN:
        data = pattern.sub(repl, data)
    return data


def create_stream(
    hass: HomeAssistant,
    stream_source: str,
    options: Mapping[str, str | bool | float],
    stream_label: str | None = None,
) -> Stream:
    """Create a stream with the specified identfier based on the source url.

    The stream_source is typically an rtsp url (though any url accepted by ffmpeg is fine) and
    options (see STREAM_OPTIONS_SCHEMA) are converted and passed into pyav / ffmpeg.

    The stream_label is a string used as an additional message in logging.
    """

    def convert_stream_options(
        hass: HomeAssistant, stream_options: Mapping[str, str | bool | float]
    ) -> tuple[dict[str, str], StreamSettings]:
        """Convert options from stream options into PyAV options and stream settings."""
        stream_settings = copy.copy(hass.data[DOMAIN][ATTR_SETTINGS])
        pyav_options: dict[str, str] = {}
        try:
            STREAM_OPTIONS_SCHEMA(stream_options)
        except vol.Invalid as exc:
            raise HomeAssistantError("Invalid stream options") from exc

        if extra_wait_time := stream_options.get(CONF_EXTRA_PART_WAIT_TIME):
            stream_settings.hls_part_timeout += extra_wait_time
        if rtsp_transport := stream_options.get(CONF_RTSP_TRANSPORT):
            assert isinstance(rtsp_transport, str)
            # The PyAV options currently match the stream CONF constants, but this
            # will not necessarily always be the case, so they are hard coded here
            pyav_options["rtsp_transport"] = rtsp_transport
        if stream_options.get(CONF_USE_WALLCLOCK_AS_TIMESTAMPS):
            pyav_options["use_wallclock_as_timestamps"] = "1"

        return pyav_options, stream_settings

    if DOMAIN not in hass.config.components:
        raise HomeAssistantError("Stream integration is not set up.")

    # Convert extra stream options into PyAV options and stream settings
    pyav_options, stream_settings = convert_stream_options(hass, options)
    # For RTSP streams, prefer TCP
    if isinstance(stream_source, str) and stream_source[:7] == "rtsp://":
        pyav_options = {
            "rtsp_flags": "prefer_tcp",
            "stimeout": "5000000",
            **pyav_options,
        }

    stream = Stream(
        hass,
        stream_source,
        pyav_options=pyav_options,
        stream_settings=stream_settings,
        stream_label=stream_label,
    )
    hass.data[DOMAIN][ATTR_STREAMS].append(stream)
    return stream


DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LL_HLS, default=True): cv.boolean,
        vol.Optional(CONF_SEGMENT_DURATION, default=6): vol.All(
            cv.positive_float, vol.Range(min=2, max=10)
        ),
        vol.Optional(CONF_PART_DURATION, default=1): vol.All(
            cv.positive_float, vol.Range(min=0.2, max=1.5)
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: DOMAIN_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)


def filter_libav_logging() -> None:
    """Filter libav logging to only log when the stream logger is at DEBUG."""

    def libav_filter(record: logging.LogRecord) -> bool:
        return logging.getLogger(__name__).isEnabledFor(logging.DEBUG)

    for logging_namespace in (
        "libav.NULL",
        "libav.h264",
        "libav.hevc",
        "libav.hls",
        "libav.mp4",
        "libav.mpegts",
        "libav.rtsp",
        "libav.tcp",
        "libav.tls",
    ):
        logging.getLogger(logging_namespace).addFilter(libav_filter)

    # Set log level to error for libav.mp4
    logging.getLogger("libav.mp4").setLevel(logging.ERROR)
    # Suppress "deprecated pixel format" WARNING
    logging.getLogger("libav.swscaler").setLevel(logging.ERROR)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up stream."""

    # Drop libav log messages if stream logging is above DEBUG
    filter_libav_logging()

    # Keep import here so that we can import stream integration without installing reqs
    # pylint: disable=import-outside-toplevel
    from .recorder import async_setup_recorder

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_ENDPOINTS] = {}
    hass.data[DOMAIN][ATTR_STREAMS] = []
    conf = DOMAIN_SCHEMA(config.get(DOMAIN, {}))
    if conf[CONF_LL_HLS]:
        assert isinstance(conf[CONF_SEGMENT_DURATION], float)
        assert isinstance(conf[CONF_PART_DURATION], float)
        hass.data[DOMAIN][ATTR_SETTINGS] = StreamSettings(
            ll_hls=True,
            min_segment_duration=conf[CONF_SEGMENT_DURATION]
            - SEGMENT_DURATION_ADJUSTER,
            part_target_duration=conf[CONF_PART_DURATION],
            hls_advance_part_limit=max(int(3 / conf[CONF_PART_DURATION]), 3),
            hls_part_timeout=2 * conf[CONF_PART_DURATION],
        )
    else:
        hass.data[DOMAIN][ATTR_SETTINGS] = STREAM_SETTINGS_NON_LL_HLS

    # Setup HLS
    hls_endpoint = async_setup_hls(hass)
    hass.data[DOMAIN][ATTR_ENDPOINTS][HLS_PROVIDER] = hls_endpoint

    # Setup Recorder
    async_setup_recorder(hass)

    async def shutdown(event: Event) -> None:
        """Stop all stream workers."""
        for stream in hass.data[DOMAIN][ATTR_STREAMS]:
            stream.keepalive = False
        if awaitables := [
            asyncio.create_task(stream.stop())
            for stream in hass.data[DOMAIN][ATTR_STREAMS]
        ]:
            await asyncio.wait(awaitables)
        _LOGGER.debug("Stopped stream workers")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class Stream:
    """Represents a single stream."""

    def __init__(
        self,
        hass: HomeAssistant,
        source: str,
        pyav_options: dict[str, str],
        stream_settings: StreamSettings,
        stream_label: str | None = None,
    ) -> None:
        """Initialize a stream."""
        self.hass = hass
        self.source = source
        self.pyav_options = pyav_options
        self._stream_settings = stream_settings
        self._stream_label = stream_label
        self.keepalive = False
        self.access_token: str | None = None
        self._start_stop_lock = asyncio.Lock()
        self._thread: threading.Thread | None = None
        self._thread_quit = threading.Event()
        self._outputs: dict[str, StreamOutput] = {}
        self._fast_restart_once = False
        self._keyframe_converter = KeyFrameConverter(hass)
        self._available: bool = True
        self._update_callback: Callable[[], None] | None = None
        self._logger = (
            logging.getLogger(f"{__package__}.stream.{stream_label}")
            if stream_label
            else _LOGGER
        )
        self._diagnostics = Diagnostics()

    def endpoint_url(self, fmt: str) -> str:
        """Start the stream and returns a url for the output format."""
        if fmt not in self._outputs:
            raise ValueError(f"Stream is not configured for format '{fmt}'")
        if not self.access_token:
            self.access_token = secrets.token_hex()
        endpoint_fmt: str = self.hass.data[DOMAIN][ATTR_ENDPOINTS][fmt]
        return endpoint_fmt.format(self.access_token)

    def outputs(self) -> Mapping[str, StreamOutput]:
        """Return a copy of the stream outputs."""
        # A copy is returned so the caller can iterate through the outputs
        # without concern about self._outputs being modified from another thread.
        return MappingProxyType(self._outputs.copy())

    def add_provider(
        self, fmt: str, timeout: int = OUTPUT_IDLE_TIMEOUT
    ) -> StreamOutput:
        """Add provider output stream."""
        if not (provider := self._outputs.get(fmt)):

            async def idle_callback() -> None:
                if (
                    not self.keepalive or fmt == RECORDER_PROVIDER
                ) and fmt in self._outputs:
                    await self.remove_provider(self._outputs[fmt])
                self.check_idle()

            provider = PROVIDERS[fmt](
                self.hass,
                IdleTimer(self.hass, timeout, idle_callback),
                self._stream_settings,
            )
            self._outputs[fmt] = provider

        return provider

    async def remove_provider(self, provider: StreamOutput) -> None:
        """Remove provider output stream."""
        if provider.name in self._outputs:
            self._outputs[provider.name].cleanup()
            del self._outputs[provider.name]

        if not self._outputs:
            await self.stop()

    def check_idle(self) -> None:
        """Reset access token if all providers are idle."""
        if all(p.idle for p in self._outputs.values()):
            self.access_token = None

    @property
    def available(self) -> bool:
        """Return False if the stream is started and known to be unavailable."""
        return self._available

    def set_update_callback(self, update_callback: Callable[[], None]) -> None:
        """Set callback to run when state changes."""
        self._update_callback = update_callback

    @callback
    def _async_update_state(self, available: bool) -> None:
        """Set state and Run callback to notify state has been updated."""
        self._available = available
        if self._update_callback:
            self._update_callback()

    async def start(self) -> None:
        """Start a stream.

        Uses an asyncio.Lock to avoid conflicts with _stop().
        """
        async with self._start_stop_lock:
            if self._thread and self._thread.is_alive():
                return
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
            self._logger.debug(
                "Started stream: %s", redact_credentials(str(self.source))
            )

    def update_source(self, new_source: str) -> None:
        """Restart the stream with a new stream source."""
        self._diagnostics.increment("update_source")
        self._logger.debug(
            "Updating stream source %s", redact_credentials(str(new_source))
        )
        self.source = new_source
        self._fast_restart_once = True
        self._thread_quit.set()

    def _run_worker(self) -> None:
        """Handle consuming streams and restart keepalive streams."""
        # Keep import here so that we can import stream integration without installing reqs
        # pylint: disable=import-outside-toplevel
        from .worker import StreamState, StreamWorkerError, stream_worker

        stream_state = StreamState(self.hass, self.outputs, self._diagnostics)
        wait_timeout = 0
        while not self._thread_quit.wait(timeout=wait_timeout):
            start_time = time.time()
            self.hass.add_job(self._async_update_state, True)
            self._diagnostics.set_value("keepalive", self.keepalive)
            self._diagnostics.increment("start_worker")
            try:
                stream_worker(
                    self.source,
                    self.pyav_options,
                    self._stream_settings,
                    stream_state,
                    self._keyframe_converter,
                    self._thread_quit,
                )
            except StreamWorkerError as err:
                self._diagnostics.increment("worker_error")
                self._logger.error("Error from stream worker: %s", str(err))

            stream_state.discontinuity()
            if not _should_retry() or self._thread_quit.is_set():
                if self._fast_restart_once:
                    # The stream source is updated, restart without any delay and reset the retry
                    # backoff for the new url.
                    wait_timeout = 0
                    self._fast_restart_once = False
                    self._thread_quit.clear()
                    continue
                break

            self.hass.add_job(self._async_update_state, False)
            # To avoid excessive restarts, wait before restarting
            # As the required recovery time may be different for different setups, start
            # with trying a short wait_timeout and increase it on each reconnection attempt.
            # Reset the wait_timeout after the worker has been up for several minutes
            if time.time() - start_time > STREAM_RESTART_RESET_TIME:
                wait_timeout = 0
            wait_timeout += STREAM_RESTART_INCREMENT
            self._diagnostics.set_value("retry_timeout", wait_timeout)
            self._logger.debug(
                "Restarting stream worker in %d seconds: %s",
                wait_timeout,
                redact_credentials(str(self.source)),
            )

        async def worker_finished() -> None:
            # The worker is no checking availability of the stream and can no longer track
            # availability so mark it as available, otherwise the frontend may not be able to
            # interact with the stream.
            if not self.available:
                self._async_update_state(True)
            # We can call remove_provider() sequentially as the wrapped _stop() function
            # which blocks internally is only called when the last provider is removed.
            for provider in self.outputs().values():
                await self.remove_provider(provider)

        self.hass.create_task(worker_finished())

    async def stop(self) -> None:
        """Remove outputs and access token."""
        self._outputs = {}
        self.access_token = None

        if not self.keepalive:
            await self._stop()

    async def _stop(self) -> None:
        """Stop worker thread.

        Uses an asyncio.Lock to avoid conflicts with start().
        """
        async with self._start_stop_lock:
            if self._thread is None:
                return
            self._thread_quit.set()
            await self.hass.async_add_executor_job(self._thread.join)
            self._thread = None
            self._logger.debug(
                "Stopped stream: %s", redact_credentials(str(self.source))
            )

    async def async_record(
        self, video_path: str, duration: int = 30, lookback: int = 5
    ) -> None:
        """Make a .mp4 recording from a provided stream."""

        # Keep import here so that we can import stream integration without installing reqs
        # pylint: disable=import-outside-toplevel
        from .recorder import RecorderOutput

        # Check for file access
        if not self.hass.config.is_allowed_path(video_path):
            raise HomeAssistantError(f"Can't write {video_path}, no access to path!")

        # Add recorder
        if recorder := self.outputs().get(RECORDER_PROVIDER):
            assert isinstance(recorder, RecorderOutput)
            raise HomeAssistantError(
                f"Stream already recording to {recorder.video_path}!"
            )
        recorder = cast(
            RecorderOutput, self.add_provider(RECORDER_PROVIDER, timeout=duration)
        )
        recorder.video_path = video_path

        await self.start()

        # Take advantage of lookback
        hls: HlsStreamOutput = cast(HlsStreamOutput, self.outputs().get(HLS_PROVIDER))
        if lookback > 0 and hls:
            num_segments = min(int(lookback // hls.target_duration), MAX_SEGMENTS)
            # Wait for latest segment, then add the lookback
            await hls.recv()
            recorder.prepend(list(hls.get_segments())[-num_segments - 1 : -1])

        self._logger.debug("Started a stream recording of %s seconds", duration)
        await recorder.async_record()

    async def async_get_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """
        Fetch an image from the Stream and return it as a jpeg in bytes.

        Calls async_get_image from KeyFrameConverter. async_get_image should only be
        called directly from the main loop and not from an executor thread as it uses
        hass.add_executor_job underneath the hood.
        """

        self.add_provider(HLS_PROVIDER)
        await self.start()
        return await self._keyframe_converter.async_get_image(
            width=width, height=height
        )

    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostics information for the stream."""
        return self._diagnostics.as_dict()


def _should_retry() -> bool:
    """Return true if worker failures should be retried, for disabling during tests."""
    return True


STREAM_OPTIONS_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_RTSP_TRANSPORT): vol.In(RTSP_TRANSPORTS),
        vol.Optional(CONF_USE_WALLCLOCK_AS_TIMESTAMPS): bool,
        vol.Optional(CONF_EXTRA_PART_WAIT_TIME): cv.positive_float,
    }
)
