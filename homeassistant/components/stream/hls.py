"""Provide functionality to stream HLS."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, cast

from aiohttp import web

from homeassistant.core import HomeAssistant, callback

from .const import (
    EXT_X_START_LL_HLS,
    EXT_X_START_NON_LL_HLS,
    FORMAT_CONTENT_TYPE,
    HLS_PROVIDER,
    MAX_SEGMENTS,
    NUM_PLAYLIST_SEGMENTS,
)
from .core import (
    PROVIDERS,
    IdleTimer,
    Segment,
    StreamOutput,
    StreamSettings,
    StreamView,
)
from .fmp4utils import get_codec_string, transform_init

if TYPE_CHECKING:
    from homeassistant.components.camera import DynamicStreamSettings

    from . import Stream


@callback
def async_setup_hls(hass: HomeAssistant) -> str:
    """Set up api endpoints."""
    hass.http.register_view(HlsPlaylistView())
    hass.http.register_view(HlsSegmentView())
    hass.http.register_view(HlsInitView())
    hass.http.register_view(HlsMasterPlaylistView())
    hass.http.register_view(HlsPartView())
    return "/api/hls/{}/master_playlist.m3u8"


@PROVIDERS.register(HLS_PROVIDER)
class HlsStreamOutput(StreamOutput):
    """Represents HLS Output formats."""

    def __init__(
        self,
        hass: HomeAssistant,
        idle_timer: IdleTimer,
        stream_settings: StreamSettings,
        dynamic_stream_settings: DynamicStreamSettings,
    ) -> None:
        """Initialize HLS output."""
        super().__init__(
            hass,
            idle_timer,
            stream_settings,
            dynamic_stream_settings,
            deque_maxlen=MAX_SEGMENTS,
        )
        self._target_duration = stream_settings.min_segment_duration

    @property
    def name(self) -> str:
        """Return provider name."""
        return HLS_PROVIDER

    def cleanup(self) -> None:
        """Handle cleanup."""
        super().cleanup()
        self._segments.clear()

    @property
    def target_duration(self) -> float:
        """Return the target duration."""
        return self._target_duration

    @callback
    def _async_put(self, segment: Segment) -> None:
        """Async put and also update the target duration.

        The target duration is calculated as the max duration of any given segment.
        Technically it should not change per the hls spec, but some cameras adjust
        their GOPs periodically so we need to account for this change.
        """
        super()._async_put(segment)
        self._target_duration = (
            max((s.duration for s in self._segments), default=segment.duration)
            or self.stream_settings.min_segment_duration
        )

    def discontinuity(self) -> None:
        """Fix incomplete segment at end of deque."""
        self._hass.loop.call_soon_threadsafe(self._async_discontinuity)

    @callback
    def _async_discontinuity(self) -> None:
        """Fix incomplete segment at end of deque in event loop."""
        # Fill in the segment duration or delete the segment if empty
        if self._segments:
            if (last_segment := self._segments[-1]).parts:
                last_segment.duration = sum(
                    part.duration for part in last_segment.parts
                )
            else:
                self._segments.pop()


class HlsMasterPlaylistView(StreamView):
    """Stream view used only for Chromecast compatibility."""

    url = r"/api/hls/{token:[a-f0-9]+}/master_playlist.m3u8"
    name = "api:stream:hls:master_playlist"
    cors_allowed = True

    @staticmethod
    def render(track: StreamOutput) -> str:
        """Render M3U8 file."""
        # Need to calculate max bandwidth as input_container.bit_rate doesn't seem to work
        # Calculate file size / duration and use a small multiplier to account for variation
        # hls spec already allows for 25% variation
        if not (segment := track.get_segment(track.sequences[-2])):
            return ""
        bandwidth = round(segment.data_size_with_init * 8 / segment.duration * 1.2)
        codecs = get_codec_string(segment.init)
        lines = [
            "#EXTM3U",
            f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},CODECS="{codecs}"',
            "playlist.m3u8",
        ]
        return "\n".join(lines) + "\n"

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str, part_num: str
    ) -> web.Response:
        """Return m3u8 playlist."""
        track = stream.add_provider(HLS_PROVIDER)
        await stream.start()
        # Make sure at least two segments are ready (last one may not be complete)
        if not track.sequences and not await track.recv():
            return web.HTTPNotFound()
        if len(track.sequences) == 1 and not await track.recv():
            return web.HTTPNotFound()
        response = web.Response(
            body=self.render(track).encode("utf-8"),
            headers={
                "Content-Type": FORMAT_CONTENT_TYPE[HLS_PROVIDER],
            },
        )
        response.enable_compression(web.ContentCoding.gzip)
        return response


class HlsPlaylistView(StreamView):
    """Stream view to serve a M3U8 stream."""

    url = r"/api/hls/{token:[a-f0-9]+}/playlist.m3u8"
    name = "api:stream:hls:playlist"
    cors_allowed = True

    @classmethod
    def render(cls, track: HlsStreamOutput) -> str:
        """Render HLS playlist file."""
        # NUM_PLAYLIST_SEGMENTS+1 because most recent is probably not yet complete
        segments = list(track.get_segments())[-(NUM_PLAYLIST_SEGMENTS + 1) :]

        # To cap the number of complete segments at NUM_PLAYLIST_SEGMENTS,
        # remove the first segment if the last segment is actually complete
        if segments[-1].complete:
            segments = segments[-NUM_PLAYLIST_SEGMENTS:]

        first_segment = segments[0]
        playlist = [
            "#EXTM3U",
            "#EXT-X-VERSION:6",
            "#EXT-X-INDEPENDENT-SEGMENTS",
            '#EXT-X-MAP:URI="init.mp4"',
            f"#EXT-X-TARGETDURATION:{track.target_duration:.0f}",
            f"#EXT-X-MEDIA-SEQUENCE:{first_segment.sequence}",
            f"#EXT-X-DISCONTINUITY-SEQUENCE:{first_segment.stream_id}",
        ]

        if track.stream_settings.ll_hls:
            playlist.extend(
                [
                    "#EXT-X-PART-INF:PART-TARGET="
                    f"{track.stream_settings.part_target_duration:.3f}",
                    "#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES,PART-HOLD-BACK="
                    f"{2 * track.stream_settings.part_target_duration:.3f}",
                    "#EXT-X-START:TIME-OFFSET=-"
                    f"{EXT_X_START_LL_HLS * track.stream_settings.part_target_duration:.3f}"
                    ",PRECISE=YES",
                ]
            )
        else:
            # Since our window doesn't have many segments, we don't want to start
            # at the beginning or we risk a behind live window exception in Exoplayer.
            # EXT-X-START is not supposed to be within 3 target durations of the end,
            # but a value as low as 1.5 doesn't seem to hurt.
            # A value below 3 may not be as useful for hls.js as many hls.js clients
            # don't autoplay. Also, hls.js uses the player parameter liveSyncDuration
            # which seems to take precedence for setting target delay. Yet it also
            # doesn't seem to hurt, so we can stick with it for now.
            playlist.append(
                "#EXT-X-START:TIME-OFFSET=-"
                f"{EXT_X_START_NON_LL_HLS * track.target_duration:.3f}"
                ",PRECISE=YES"
            )

        last_stream_id = first_segment.stream_id

        # Add playlist sections for completed segments
        # Enumeration used to only include EXT-X-PART data for last 3 segments.
        # The RFC seems to suggest removing parts after 3 full segments, but Apple's
        # own example shows removing after 2 full segments and 1 part one.
        for i, segment in enumerate(segments[:-1], 3 - len(segments)):
            playlist.append(
                segment.render_hls(
                    last_stream_id=last_stream_id,
                    render_parts=i >= 0 and track.stream_settings.ll_hls,
                    add_hint=False,
                )
            )
            last_stream_id = segment.stream_id

        playlist.append(
            segments[-1].render_hls(
                last_stream_id=last_stream_id,
                render_parts=track.stream_settings.ll_hls,
                add_hint=track.stream_settings.ll_hls,
            )
        )

        return "\n".join(playlist) + "\n"

    @staticmethod
    def bad_request(blocking: bool, target_duration: float) -> web.Response:
        """Return a HTTP Bad Request response."""
        return web.Response(
            body=None,
            status=HTTPStatus.BAD_REQUEST,
        )

    @staticmethod
    def not_found(blocking: bool, target_duration: float) -> web.Response:
        """Return a HTTP Not Found response."""
        return web.Response(
            body=None,
            status=HTTPStatus.NOT_FOUND,
        )

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str, part_num: str
    ) -> web.Response:
        """Return m3u8 playlist."""
        track: HlsStreamOutput = cast(
            HlsStreamOutput, stream.add_provider(HLS_PROVIDER)
        )
        await stream.start()

        hls_msn: str | int | None = request.query.get("_HLS_msn")
        hls_part: str | int | None = request.query.get("_HLS_part")
        blocking_request = bool(hls_msn or hls_part)

        # If the Playlist URI contains an _HLS_part directive but no _HLS_msn
        # directive, the Server MUST return Bad Request, such as HTTP 400.
        if hls_msn is None and hls_part:
            return web.HTTPBadRequest()

        hls_msn = int(hls_msn or 0)

        # If the _HLS_msn is greater than the Media Sequence Number of the last
        # Media Segment in the current Playlist plus two, or if the _HLS_part
        # exceeds the last Part Segment in the current Playlist by the
        # Advance Part Limit, then the server SHOULD immediately return Bad
        # Request, such as HTTP 400.
        if hls_msn > track.last_sequence + 2:
            return self.bad_request(blocking_request, track.target_duration)

        if hls_part is None:
            # We need to wait for the whole segment, so effectively the next msn
            hls_part = -1
            hls_msn += 1
        else:
            hls_part = int(hls_part)

        while hls_msn > track.last_sequence:
            if not await track.recv():
                return self.not_found(blocking_request, track.target_duration)
        if track.last_segment is None:
            return self.not_found(blocking_request, 0)
        if (
            (last_segment := track.last_segment)
            and hls_msn == last_segment.sequence
            and hls_part
            >= len(last_segment.parts)
            - 1
            + track.stream_settings.hls_advance_part_limit
        ):
            return self.bad_request(blocking_request, track.target_duration)

        # Receive parts until msn and part are met
        while (
            (last_segment := track.last_segment)
            and hls_msn == last_segment.sequence
            and hls_part >= len(last_segment.parts)
        ):
            if not await track.part_recv(
                timeout=track.stream_settings.hls_part_timeout
            ):
                return self.not_found(blocking_request, track.target_duration)
        # Now we should have msn.part >= hls_msn.hls_part. However, in the case
        # that we have a rollover part request from the previous segment, we need
        # to make sure that the new segment has a part. From 6.2.5.2 of the RFC:
        # If the Client requests a Part Index greater than that of the final
        # Partial Segment of the Parent Segment, the Server MUST treat the
        # request as one for Part Index 0 of the following Parent Segment.
        if hls_msn + 1 == last_segment.sequence:
            if not (previous_segment := track.get_segment(hls_msn)) or (
                hls_part >= len(previous_segment.parts)
                and not last_segment.parts
                and not await track.part_recv(
                    timeout=track.stream_settings.hls_part_timeout
                )
            ):
                return self.not_found(blocking_request, track.target_duration)

        response = web.Response(
            body=self.render(track).encode("utf-8"),
            headers={
                "Content-Type": FORMAT_CONTENT_TYPE[HLS_PROVIDER],
            },
        )
        response.enable_compression(web.ContentCoding.gzip)
        return response


class HlsInitView(StreamView):
    """Stream view to serve HLS init.mp4."""

    url = r"/api/hls/{token:[a-f0-9]+}/init.mp4"
    name = "api:stream:hls:init"
    cors_allowed = True

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str, part_num: str
    ) -> web.Response:
        """Return init.mp4."""
        track = stream.add_provider(HLS_PROVIDER)
        if not (segments := track.get_segments()) or not (body := segments[0].init):
            return web.HTTPNotFound()
        return web.Response(
            body=transform_init(body, stream.dynamic_stream_settings.orientation),
            headers={"Content-Type": "video/mp4"},
        )


class HlsPartView(StreamView):
    """Stream view to serve a HLS fmp4 segment."""

    url = r"/api/hls/{token:[a-f0-9]+}/segment/{sequence:\d+}.{part_num:\d+}.m4s"
    name = "api:stream:hls:part"
    cors_allowed = True

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str, part_num: str
    ) -> web.Response:
        """Handle part."""
        track: HlsStreamOutput = cast(
            HlsStreamOutput, stream.add_provider(HLS_PROVIDER)
        )
        track.idle_timer.awake()
        # Ensure that we have a segment. If the request is from a hint for part 0
        # of a segment, there is a small chance it may have arrived before the
        # segment has been put. If this happens, wait for one part and retry.
        if not (
            (segment := track.get_segment(int(sequence)))
            or (
                await track.part_recv(timeout=track.stream_settings.hls_part_timeout)
                and (segment := track.get_segment(int(sequence)))
            )
        ):
            return web.Response(
                body=None,
                status=HTTPStatus.NOT_FOUND,
            )
        # If the part is ready or has been hinted,
        if int(part_num) == len(segment.parts):
            await track.part_recv(timeout=track.stream_settings.hls_part_timeout)
        if int(part_num) >= len(segment.parts):
            return web.HTTPRequestRangeNotSatisfiable()
        return web.Response(
            body=segment.parts[int(part_num)].data,
            headers={
                "Content-Type": "video/iso.segment",
            },
        )


class HlsSegmentView(StreamView):
    """Stream view to serve a HLS fmp4 segment."""

    url = r"/api/hls/{token:[a-f0-9]+}/segment/{sequence:\d+}.m4s"
    name = "api:stream:hls:segment"
    cors_allowed = True

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str, part_num: str
    ) -> web.StreamResponse:
        """Handle segments."""
        track: HlsStreamOutput = cast(
            HlsStreamOutput, stream.add_provider(HLS_PROVIDER)
        )
        track.idle_timer.awake()
        # Ensure that we have a segment. If the request is from a hint for part 0
        # of a segment, there is a small chance it may have arrived before the
        # segment has been put. If this happens, wait for one part and retry.
        if not (
            (segment := track.get_segment(int(sequence)))
            or (
                await track.part_recv(timeout=track.stream_settings.hls_part_timeout)
                and (segment := track.get_segment(int(sequence)))
            )
        ):
            return web.Response(
                body=None,
                status=HTTPStatus.NOT_FOUND,
            )
        return web.Response(
            body=segment.get_data(),
            headers={
                "Content-Type": "video/iso.segment",
            },
        )
