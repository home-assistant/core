"""Provide functionality to stream HLS."""
from aiohttp import web

from homeassistant.core import callback

from .const import (
    EXT_X_START,
    FORMAT_CONTENT_TYPE,
    HLS_PROVIDER,
    MAX_SEGMENTS,
    NUM_PLAYLIST_SEGMENTS,
)
from .core import PROVIDERS, HomeAssistant, IdleTimer, StreamOutput, StreamView
from .fmp4utils import get_codec_string


@callback
def async_setup_hls(hass):
    """Set up api endpoints."""
    hass.http.register_view(HlsPlaylistView())
    hass.http.register_view(HlsSegmentView())
    hass.http.register_view(HlsInitView())
    hass.http.register_view(HlsMasterPlaylistView())
    return "/api/hls/{}/master_playlist.m3u8"


class HlsMasterPlaylistView(StreamView):
    """Stream view used only for Chromecast compatibility."""

    url = r"/api/hls/{token:[a-f0-9]+}/master_playlist.m3u8"
    name = "api:stream:hls:master_playlist"
    cors_allowed = True

    @staticmethod
    def render(track):
        """Render M3U8 file."""
        # Need to calculate max bandwidth as input_container.bit_rate doesn't seem to work
        # Calculate file size / duration and use a small multiplier to account for variation
        # hls spec already allows for 25% variation
        segment = track.get_segment(track.sequences[-1])
        bandwidth = round(
            (len(segment.init) + len(segment.moof_data)) * 8 / segment.duration * 1.2
        )
        codecs = get_codec_string(segment.init)
        lines = [
            "#EXTM3U",
            f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},CODECS="{codecs}"',
            "playlist.m3u8",
        ]
        return "\n".join(lines) + "\n"

    async def handle(self, request, stream, sequence):
        """Return m3u8 playlist."""
        track = stream.add_provider(HLS_PROVIDER)
        stream.start()
        # Wait for a segment to be ready
        if not track.sequences and not await track.recv():
            return web.HTTPNotFound()
        headers = {"Content-Type": FORMAT_CONTENT_TYPE[HLS_PROVIDER]}
        return web.Response(body=self.render(track).encode("utf-8"), headers=headers)


class HlsPlaylistView(StreamView):
    """Stream view to serve a M3U8 stream."""

    url = r"/api/hls/{token:[a-f0-9]+}/playlist.m3u8"
    name = "api:stream:hls:playlist"
    cors_allowed = True

    @staticmethod
    def render_preamble(track):
        """Render preamble."""
        return [
            "#EXT-X-VERSION:6",
            f"#EXT-X-TARGETDURATION:{track.target_duration}",
            '#EXT-X-MAP:URI="init.mp4"',
        ]

    @staticmethod
    def render_playlist(track):
        """Render playlist."""
        segments = list(track.get_segments())[-NUM_PLAYLIST_SEGMENTS:]

        if not segments:
            return []

        first_segment = segments[0]
        playlist = [
            f"#EXT-X-MEDIA-SEQUENCE:{first_segment.sequence}",
            f"#EXT-X-DISCONTINUITY-SEQUENCE:{first_segment.stream_id}",
            "#EXT-X-PROGRAM-DATE-TIME:"
            + first_segment.start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z",
            # Since our window doesn't have many segments, we don't want to start
            # at the beginning or we risk a behind live window exception in exoplayer.
            # EXT-X-START is not supposed to be within 3 target durations of the end,
            # but this seems ok
            f"#EXT-X-START:TIME-OFFSET=-{EXT_X_START * track.target_duration:.3f},PRECISE=YES",
        ]

        last_stream_id = first_segment.stream_id
        for segment in segments:
            if last_stream_id != segment.stream_id:
                playlist.extend(
                    [
                        "#EXT-X-DISCONTINUITY",
                        "#EXT-X-PROGRAM-DATE-TIME:"
                        + segment.start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                        + "Z",
                    ]
                )
            playlist.extend(
                [
                    f"#EXTINF:{float(segment.duration):.04f},",
                    f"./segment/{segment.sequence}.m4s",
                ]
            )
            last_stream_id = segment.stream_id

        return playlist

    def render(self, track):
        """Render M3U8 file."""
        lines = ["#EXTM3U"] + self.render_preamble(track) + self.render_playlist(track)
        return "\n".join(lines) + "\n"

    async def handle(self, request, stream, sequence):
        """Return m3u8 playlist."""
        track = stream.add_provider(HLS_PROVIDER)
        stream.start()
        # Wait for a segment to be ready
        if not track.sequences and not await track.recv():
            return web.HTTPNotFound()
        headers = {"Content-Type": FORMAT_CONTENT_TYPE[HLS_PROVIDER]}
        response = web.Response(
            body=self.render(track).encode("utf-8"), headers=headers
        )
        response.enable_compression(web.ContentCoding.gzip)
        return response


class HlsInitView(StreamView):
    """Stream view to serve HLS init.mp4."""

    url = r"/api/hls/{token:[a-f0-9]+}/init.mp4"
    name = "api:stream:hls:init"
    cors_allowed = True

    async def handle(self, request, stream, sequence):
        """Return init.mp4."""
        track = stream.add_provider(HLS_PROVIDER)
        if not (segments := track.get_segments()):
            return web.HTTPNotFound()
        headers = {"Content-Type": "video/mp4"}
        return web.Response(body=segments[0].init, headers=headers)


class HlsSegmentView(StreamView):
    """Stream view to serve a HLS fmp4 segment."""

    url = r"/api/hls/{token:[a-f0-9]+}/segment/{sequence:\d+}.m4s"
    name = "api:stream:hls:segment"
    cors_allowed = True

    async def handle(self, request, stream, sequence):
        """Return fmp4 segment."""
        track = stream.add_provider(HLS_PROVIDER)
        if not (segment := track.get_segment(int(sequence))):
            return web.HTTPNotFound()
        headers = {"Content-Type": "video/iso.segment"}
        return web.Response(
            body=segment.moof_data,
            headers=headers,
        )


@PROVIDERS.register(HLS_PROVIDER)
class HlsStreamOutput(StreamOutput):
    """Represents HLS Output formats."""

    def __init__(self, hass: HomeAssistant, idle_timer: IdleTimer) -> None:
        """Initialize recorder output."""
        super().__init__(hass, idle_timer, deque_maxlen=MAX_SEGMENTS)

    @property
    def name(self) -> str:
        """Return provider name."""
        return HLS_PROVIDER
