"""
Provide functionality to stream camera source.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/stream/
"""
import asyncio
import io
import logging
import threading
from typing import List, Any

import attr
from aiohttp import web
import voluptuous as vol

from homeassistant.auth.util import generate_secret
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_PLATFORM, ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass
from homeassistant.setup import (
    async_setup_component, async_prepare_setup_platform)

REQUIREMENTS = ['av==6.1.2', 'pillow==5.4.1']

_LOGGER = logging.getLogger(__name__)

ATTR_OPTIONS = 'options'
ATTR_ENDPOINTS = 'endpoints'
ATTR_STREAMS = 'streams'

CONF_BASE_URL = 'base_url'
CONF_PRELOAD = 'preload'

ALL_PLATFORMS = ['hls', 'mjpeg']

DEPENDENCIES = ['http', 'camera']
DOMAIN = 'stream'
DOMAIN_CAMERA = 'camera'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BASE_URL): cv.string,
        vol.Optional(CONF_PRELOAD, default=False): cv.boolean,
        vol.Optional(CONF_PLATFORM, default=ALL_PLATFORMS): vol.All(
            cv.ensure_list, [vol.In(ALL_PLATFORMS)]),
    }),
}, extra=vol.ALLOW_EXTRA)

SCHEMA_SERVICE_OPEN = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Optional(ATTR_OPTIONS): dict,
})

SCHEMA_SERVICE_CLEAR_CACHE = vol.Schema({})


@bind_hass
async def async_request_stream(hass, entity_id):
    """Set up stream with token."""
    if DOMAIN not in hass.config.components:
        await async_setup_component(hass, DOMAIN, {
            DOMAIN: {
                CONF_PRELOAD: False,
                CONF_PLATFORM: ALL_PLATFORMS
            }
        })

    try:
        stream = hass.data[DOMAIN][ATTR_STREAMS][entity_id]
        stream.access_token = generate_secret()
        stream.start()
        return stream.access_token
    except KeyError:
        _LOGGER.error("No stream found for %s", entity_id)

    raise HomeAssistantError('Unable to get stream')


async def async_setup(hass, config):
    """Set up stream."""
    conf = config[DOMAIN] if config.get(DOMAIN, {}) else {}
    # base_url = conf.get(CONF_BASE_URL) or hass.config.api.base_url
    preload = conf.get(CONF_PRELOAD)
    platforms = conf.get(CONF_PLATFORM)

    hass.data[DOMAIN] = {}
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

    setup_tasks = [async_setup_platform(p_type, {}) for p_type in platforms]

    if setup_tasks:
        await asyncio.wait(setup_tasks, loop=hass.loop)

    # Register camera streams
    component = hass.data.get(DOMAIN_CAMERA)

    if component is None:
        raise HomeAssistantError('Camera component not set up')

    for camera in component.entities:
        if camera.stream_source:
            hass.data[DOMAIN][ATTR_STREAMS][camera.entity_id] = Stream(
                hass, camera.stream_source, preload=preload)

    return True


@attr.s
class StreamBuffer:
    """Represent a segment."""

    # pylint: disable=no-name-in-module
    from av import CodecContext
    from av.container import OutputContainer
    from av.video.stream import VideoStream

    segment = attr.ib(type=io.BytesIO)
    output = attr.ib(type=OutputContainer)
    vstream = attr.ib(type=VideoStream)


def stream_worker(hass, stream, quit_event):
    """Handle consuming streams."""
    import av
    try:
        video_stream = stream.container.streams.video[0]
    except KeyError:
        hass.getLogger().error("Stream has no video")
        return
    outputs = {}

    first_packet = True
    sequence = 1

    while not quit_event.is_set():
        packet = next(stream.container.demux(video_stream))

        # We need to skip the "flushing" packets that `demux` generates.
        if packet.dts is None:
            continue

        # Mux on every keyframe
        if (packet.stream.type == 'video'
                and packet.is_keyframe and not first_packet):
            segment_duration = (packet.pts * packet.time_base) / sequence
            for fmt, buffer in outputs.items():
                buffer.output.close()
                asyncio.run_coroutine_threadsafe(
                    stream.outputs[fmt].put(Segment(
                        sequence, buffer.segment, segment_duration
                    )), hass.loop)
            outputs = {}
            sequence += 1

        # Initialize outputs
        if not outputs:
            for stream_output in stream.outputs.values():
                if video_stream.name != stream_output.video_codec:
                    continue

                segment = io.BytesIO()
                output = av.open(
                    segment, mode='w', format=stream_output.format)
                vstream = output.add_stream(
                    stream_output.video_codec, video_stream.rate)
                # Fix format
                vstream.codec_context.format = \
                    video_stream.codec_context.format
                outputs[stream_output.format] = StreamBuffer(
                    segment, output, vstream)

        # First video packet tends to have a weird dts/pts
        if packet.stream.type == 'video' and first_packet:
            packet.dts = 0
            packet.pts = 0
            first_packet = False

        # We need to assign the packet to the new stream.
        if packet.stream.type == 'video':
            for buffer in outputs.values():
                packet.stream = buffer.vstream
                buffer.output.mux(packet)


class Stream:
    """Represents a single stream."""

    # pylint: disable=dangerous-default-value
    def __init__(self, hass, source, options={},
                 preload=False):
        """Initialize a stream."""
        self.hass = hass
        self.source = source
        self.options = options
        self.preload = preload
        self.access_token = None
        self.__container = None
        self.__thread = None
        self.__thread_quit = None
        self.__outputs = {}

        if self.preload:
            self.start()

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

        if not self.preload:
            self.stop()

    def stop(self):
        """Stop worker thread."""
        if self.__thread is not None:
            self.__thread_quit.set()
            self.__thread.join()
            self.__thread = None
            self.__container = None


@attr.s
class Segment:
    """Represent a segment."""

    sequence = attr.ib(type=int)
    segment = attr.ib(type=io.BytesIO)
    duration = attr.ib(type=float)


class StreamOutput:
    """Represents a stream output."""

    num_segments = 3

    def __init__(self) -> None:
        """Initialize a stream output."""
        self.__cursor = None
        self.__event = asyncio.Event()
        self.__segments = []

    @property
    def format(self) -> str:
        """Return container format."""
        return None

    @property
    def audio_codec(self) -> str:
        """Return desired audio codec."""
        return None

    @property
    def video_codec(self) -> str:
        """Return desired video codec."""
        return None

    @property
    def segments(self) -> List[int]:
        """Return current sequence from segments."""
        return [s.sequence for s in self.__segments]

    @property
    def target_duration(self) -> int:
        """Return the average duration of the segments in seconds."""
        durations = [s.duration for s in self.__segments]
        return round(sum(durations) // len(self.__segments)) or 1

    def get_segment(self, sequence: int = None) -> Any:
        """Retrieve a specific segment, or the whole list."""
        if not sequence:
            return self.__segments

        for segment in self.__segments:
            if segment.sequence == sequence:
                return segment
        return None

    async def recv(self) -> Segment:
        """Wait for and retrieve the latest segment."""
        if self.__cursor is None or self.__cursor <= max(self.segments):
            await self.__event.wait()
        segment = self.__segments[-1]
        self.__cursor = segment.sequence
        return segment

    async def put(self, segment: Segment) -> None:
        """Store output."""
        self.__segments.append(segment)
        if len(self.__segments) > self.num_segments:
            self.__segments = self.__segments[-self.num_segments:]
        self.__event.set()
        self.__event.clear()


class StreamView(HomeAssistantView):
    """Base CameraView."""

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
        """Handle the camera request."""
        raise NotImplementedError()
