"""
Provide functionality to stream HLS.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/stream/hls
"""
import datetime

from aiohttp import web

from homeassistant.components.stream import StreamView, StreamOutput


async def async_setup_platform(hass):
    """Set up api endpoints."""
    hass.http.register_view(HlsPlaylistView())
    hass.http.register_view(HlsSegmentView())
    return '/api/hls/{}/playlist.m3u8'


class HlsPlaylistView(StreamView):
    """Camera view to serve a M3U8 stream."""

    url = '/api/hls/{token}/playlist.m3u8'
    name = 'api:camera:hls:playlist'

    async def handle(self, request, stream, sequence):
        """Return m3u8 playlist."""
        renderer = M3U8Renderer(stream)
        track = stream.add_provider(HlsStreamOutput())
        # Wait for a segment to be ready
        if not track.segments:
            await track.recv()
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/vnd.apple.mpegurl',
            'Content-Disposition': "inline; filename=\"playlist.m3u8\"",
        }
        return web.Response(body=renderer.render(
            track, datetime.datetime.utcnow()
            ).encode("utf-8"), headers=headers)


class HlsSegmentView(StreamView):
    """Camera view to serve a MPEG2TS segment."""

    url = '/api/hls/{token}/segment/{sequence}.ts'
    name = 'api:camera:hls:segment'

    async def handle(self, request, stream, sequence):
        """Return mpegts segment."""
        track = stream.add_provider(HlsStreamOutput())
        segment = track.get_segment(int(sequence))
        if not segment:
            return web.HTTPNotFound()
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Accept-Ranges': 'bytes',
            'Content-Type': 'video/mp2t',
            'Content-Length': str(segment.segment.getbuffer().nbytes),
            'Content-Disposition': "inline; filename=\"%d.ts\"" % sequence,
        }
        return web.Response(body=segment.segment.getvalue(), headers=headers)


class M3U8Renderer:
    """M3U8 Render Helper."""

    def __init__(self, stream, version=3, lookback=4):
        """Initialize renderer."""
        self.stream = stream
        self.version = version
        self.lookback = lookback

    def render_preamble(self, track):
        """Render preamble."""
        return [
            "#EXT-X-VERSION:{}".format(self.version),
            "#EXT-X-TARGETDURATION:{}".format(track.target_duration),
        ]

    def render_segment(self, segment):
        """Render segment."""
        return [
            "#EXTINF:{:.04},".format(float(segment.duration)),
            "/api/hls/{}/segment/{}.ts".format(
                self.stream.access_token,
                segment.sequence),
        ]

    def render_playlist(self, track, start_time):
        """Render playlist."""
        segments = track.segments

        if not segments:
            return []

        playlist = ["#EXT-X-MEDIA-SEQUENCE:{}".format(segments[0])]

        for sequence in segments:
            segment = track.get_segment(sequence)
            playlist.extend(self.render_segment(segment))

        return playlist

    def render(self, track, start_time):
        """Render M3U8 file."""
        lines = (
            ["#EXTM3U"] +
            self.render_preamble(track) +
            self.render_playlist(track, start_time)
        )
        return "\n".join(lines) + "\n"


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
