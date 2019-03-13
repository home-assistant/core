"""
Provide functionality to stream HLS.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/stream/hls
"""
from aiohttp import web

from homeassistant.core import callback
from homeassistant.util.dt import utcnow

from .const import FORMAT_CONTENT_TYPE
from .core import StreamView, StreamOutput, PROVIDERS


@callback
def async_setup_hls(hass):
    """Set up api endpoints."""
    hass.http.register_view(HlsPlaylistView())
    hass.http.register_view(HlsSegmentView())
    return '/api/hls/{}/playlist.m3u8'


class HlsPlaylistView(StreamView):
    """Stream view to serve a M3U8 stream."""

    url = r'/api/hls/{token:[a-f0-9]+}/playlist.m3u8'
    name = 'api:stream:hls:playlist'
    cors_allowed = True

    async def handle(self, request, stream, sequence):
        """Return m3u8 playlist."""
        renderer = M3U8Renderer(stream)
        track = stream.add_provider('hls')
        stream.start()
        # Wait for a segment to be ready
        if not track.segments:
            await track.recv()
        headers = {
            'Content-Type': FORMAT_CONTENT_TYPE['hls']
        }
        return web.Response(body=renderer.render(
            track, utcnow()).encode("utf-8"), headers=headers)


class HlsSegmentView(StreamView):
    """Stream view to serve a MPEG2TS segment."""

    url = r'/api/hls/{token:[a-f0-9]+}/segment/{sequence:\d+}.ts'
    name = 'api:stream:hls:segment'
    cors_allowed = True

    async def handle(self, request, stream, sequence):
        """Return mpegts segment."""
        track = stream.add_provider('hls')
        segment = track.get_segment(int(sequence))
        if not segment:
            return web.HTTPNotFound()
        headers = {
            'Content-Type': 'video/mp2t'
        }
        return web.Response(body=segment.segment.getvalue(), headers=headers)


class M3U8Renderer:
    """M3U8 Render Helper."""

    def __init__(self, stream):
        """Initialize renderer."""
        self.stream = stream

    @staticmethod
    def render_preamble(track):
        """Render preamble."""
        return [
            "#EXT-X-VERSION:3",
            "#EXT-X-TARGETDURATION:{}".format(track.target_duration),
        ]

    @staticmethod
    def render_playlist(track, start_time):
        """Render playlist."""
        segments = track.segments

        if not segments:
            return []

        playlist = ["#EXT-X-MEDIA-SEQUENCE:{}".format(segments[0])]

        for sequence in segments:
            segment = track.get_segment(sequence)
            playlist.extend([
                "#EXTINF:{:.04},".format(float(segment.duration)),
                "./segment/{}.ts".format(segment.sequence),
            ])

        return playlist

    def render(self, track, start_time):
        """Render M3U8 file."""
        lines = (
            ["#EXTM3U"] +
            self.render_preamble(track) +
            self.render_playlist(track, start_time)
        )
        return "\n".join(lines) + "\n"


@PROVIDERS.register('hls')
class HlsStreamOutput(StreamOutput):
    """Represents HLS Output formats."""

    @property
    def format(self) -> str:
        """Return container format."""
        return 'mpegts'

    @property
    def audio_codec(self) -> str:
        """Return desired audio codec."""
        return 'aac'

    @property
    def video_codec(self) -> str:
        """Return desired video codec."""
        return 'h264'
