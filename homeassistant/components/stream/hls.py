"""Provide functionality to stream HLS."""
from __future__ import annotations

from copy import copy
import itertools
import logging
from typing import TYPE_CHECKING

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
    StreamConstants,
    StreamOutput,
    StreamView,
)
from .fmp4utils import get_codec_string

if TYPE_CHECKING:
    from . import Stream

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_hls(hass: HomeAssistant) -> str:
    """Set up api endpoints."""
    hass.http.register_view(HlsPlaylistView())
    hass.http.register_view(HlsSegmentView())
    hass.http.register_view(HlsInitView())
    hass.http.register_view(HlsMasterPlaylistView())
    return "/api/hls/{}/master_playlist.m3u8"


@PROVIDERS.register(HLS_PROVIDER)
class HlsStreamOutput(StreamOutput):
    """Represents HLS Output formats."""

    def __init__(self, hass: HomeAssistant, idle_timer: IdleTimer) -> None:
        """Initialize HLS output."""
        super().__init__(hass, idle_timer, deque_maxlen=MAX_SEGMENTS)

    @property
    def name(self) -> str:
        """Return provider name."""
        return HLS_PROVIDER


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
        self, request: web.Request, stream: Stream, sequence: str
    ) -> web.Response:
        """Return m3u8 playlist."""
        track = stream.add_provider(HLS_PROVIDER)
        stream.start()
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
    def render_current_segment(
        cls, segment: Segment, ll_hls: bool, last_stream_id: int
    ) -> str:
        """Render the most recent segment of a hls playlist including the hint.

        This method is run on every playlist request and the output is not saved.
        """
        # Create a copy of the segment with the parts frozen so we can iterate safely
        segment_copy = copy(segment)
        segment_copy.parts_by_http_range = segment_copy.parts_by_http_range.copy()
        (
            segment.hls_playlist,
            segment.hls_playlist_parts,
            segment.hls_num_parts_rendered,
            segment.hls_playlist_complete,
        ) = cls.render_segment(segment_copy, ll_hls, last_stream_id)
        rendered = segment.hls_playlist.format(segment.hls_playlist_parts)
        playlist = [rendered] if rendered else []

        # Add preload hint
        # pylint: disable=undefined-loop-variable
        if ll_hls:
            if segment_copy.complete:  # Next part belongs to next segment
                sequence = segment_copy.sequence + 1
                start = 0
            else:  # Next part is in the same segment
                sequence = segment_copy.sequence
                start = segment_copy.data_size_without_init
            playlist.append(
                f'#EXT-X-PRELOAD-HINT:TYPE=PART,URI="./segment/{sequence}'
                f'.m4s",BYTERANGE-START={start}'
            )
        return "\n".join(playlist)

    @staticmethod
    def render_segment(
        segment: Segment, ll_hls: bool, last_stream_id: int
    ) -> tuple[str, str, int, bool]:
        """Render a segment.

        Return a base string, a ll_hls string that can be interjected, the number of parts
        rendered so far, and a bool that indicates if the rendering for the segment is complete.
        """
        playlist = [segment.hls_playlist] if segment.hls_playlist else []
        playlist_parts = (
            [segment.hls_playlist_parts] if segment.hls_playlist_parts else []
        )
        if not playlist:
            if last_stream_id != segment.stream_id:
                playlist = [
                    "#EXT-X-DISCONTINUITY",
                    "#EXT-X-PROGRAM-DATE-TIME:"
                    + segment.start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                    + "Z",
                ]
            playlist.append("{}")
        if ll_hls:
            for http_range_start, part in itertools.islice(
                segment.parts_by_http_range.items(),
                segment.hls_num_parts_rendered,
                None,
            ):
                playlist_parts.append(
                    f"#EXT-X-PART:DURATION={part.duration:.3f},URI="
                    f'"./segment/{segment.sequence}.m4s",BYTERANGE="{len(part.data)}'
                    f'@{http_range_start}"{",INDEPENDENT=YES" if part.has_keyframe else ""}'
                )
        if segment.complete:
            playlist.pop()
            playlist.extend(
                [
                    # Squeeze the placeholder on the same line as #EXTINF
                    # just to keep tidy when there are no parts
                    "{}" + f"#EXTINF:{segment.duration:.3f},",
                    f"./segment/{segment.sequence}.m4s",
                ]
            )
            # Append another line to parts because we don't include a newline before #EXTINF
            playlist_parts.append("")
        return (
            "\n".join(playlist),
            "\n".join(playlist_parts),
            len(segment.parts_by_http_range),
            segment.complete,
        )

    @classmethod
    def render(cls, track: StreamOutput, ll_hls: bool) -> str:
        """Render HLS playlist file."""
        # NUM_PLAYLIST_SEGMENTS+1 because most recent is probably not yet complete
        segments = list(track.get_segments())[-(NUM_PLAYLIST_SEGMENTS + 1) :]

        # Create a copy of the last segment with the parts frozen for rendering playlist
        segments[-1] = copy(segments[-1])
        segments[-1].parts_by_http_range = segments[-1].parts_by_http_range.copy()

        # To cap the number of complete segments at NUM_PLAYLIST_SEGMENTS,
        # remove the first segment if the last segment is actually complete
        if segments[-1].complete:
            segments = segments[-NUM_PLAYLIST_SEGMENTS:]

        # The track may have been updated since we froze it, but this should be good enough
        target_duration = track.target_duration

        first_segment = segments[0]
        playlist = [
            "#EXTM3U",
            "#EXT-X-VERSION:6",
            "#EXT-X-INDEPENDENT-SEGMENTS",
            '#EXT-X-MAP:URI="init.mp4"',
            f"#EXT-X-TARGETDURATION:{target_duration:.0f}",
            f"#EXT-X-MEDIA-SEQUENCE:{first_segment.sequence}",
            f"#EXT-X-DISCONTINUITY-SEQUENCE:{first_segment.stream_id}",
            "#EXT-X-PROGRAM-DATE-TIME:"
            + first_segment.start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z",
        ]

        if ll_hls:
            part_duration = float(
                max(
                    (
                        p.duration
                        for s in segments
                        for p in s.parts_by_http_range.values()
                    ),
                    default=StreamConstants.TARGET_PART_DURATION,
                )
            )
            playlist.extend(
                [
                    f"#EXT-X-PART-INF:PART-TARGET={part_duration:.3f}",
                    f"#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES,PART-HOLD-BACK={2*part_duration:.3f}",
                    f"#EXT-X-START:TIME-OFFSET=-{EXT_X_START_LL_HLS*part_duration:.3f},PRECISE=YES",
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
                f"#EXT-X-START:TIME-OFFSET=-{EXT_X_START_NON_LL_HLS*track.target_duration:.3f},PRECISE=YES"
            )

        last_stream_id = first_segment.stream_id

        # Add playlist sections for completed segments
        # Enumeration used to only include EXT-X-PART data for last 3 segments.
        # The RFC seems to suggest removing parts after 3 full segments, but Apple's
        # own example shows removing after 2 full segments and 1 part one.
        for i, segment in enumerate(segments[:-1], 3 - len(segments)):
            if not segment.hls_playlist_complete:
                (
                    segment.hls_playlist,
                    segment.hls_playlist_parts,
                    segment.hls_num_parts_rendered,
                    segment.hls_playlist_complete,
                ) = cls.render_segment(segment, ll_hls, last_stream_id)
            playlist.append(
                segment.hls_playlist.format(
                    segment.hls_playlist_parts if i >= 0 else ""
                )
            )
            last_stream_id = segment.stream_id

        playlist.append(
            cls.render_current_segment(segments[-1], ll_hls, last_stream_id)
        )

        return "\n".join(playlist) + "\n"

    @staticmethod
    def bad_request(blocking: bool, target_duration: float) -> web.Response:
        """Return a HTTP Bad Request response."""
        return web.Response(
            body=None,
            status=400,
            headers={
                "Cache-Control": f"max-age={(4 if blocking else 1)*target_duration:.0f}"
            },
        )

    @staticmethod
    def not_found(blocking: bool, target_duration: float) -> web.Response:
        """Return a HTTP Not Found response."""
        return web.Response(
            body=None,
            status=404,
            headers={
                "Cache-Control": f"max-age={(4 if blocking else 1)*target_duration:.0f}"
            },
        )

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str
    ) -> web.Response:
        """Return m3u8 playlist."""
        track = stream.add_provider(HLS_PROVIDER)
        stream.start()

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
            >= len(last_segment.parts_by_http_range)
            - 1
            + StreamConstants.HLS_ADVANCE_PART_LIMIT
        ):
            return self.bad_request(blocking_request, track.target_duration)

        # Receive parts until msn and part are met
        while (
            (last_segment := track.last_segment)
            and hls_msn == last_segment.sequence
            and hls_part >= len(last_segment.parts_by_http_range)
        ):
            if not await track.part_recv(timeout=StreamConstants.HLS_PART_TIMEOUT):
                return self.not_found(blocking_request, track.target_duration)
        # Now we should have msn.part >= hls_msn.hls_part. However, in the case
        # that we have a rollover part request from the previous segment, we need
        # to make sure that the new segment has a part. From the RFC:
        # If the Client requests a Part Index greater than that of the final
        # Partial Segment of the Parent Segment, the Server MUST treat the
        # request as one for Part Index 0 of the following Parent Segment.
        if hls_msn + 1 == last_segment.sequence:
            if not (previous_segment := track.get_segment(hls_msn)) or (
                hls_part >= len(previous_segment.parts_by_http_range)
                and not last_segment.parts_by_http_range
                and not await track.part_recv(timeout=StreamConstants.HLS_PART_TIMEOUT)
            ):
                return self.not_found(blocking_request, track.target_duration)

        response = web.Response(
            body=self.render(track, StreamConstants.LL_HLS).encode("utf-8"),
            headers={
                "Content-Type": FORMAT_CONTENT_TYPE[HLS_PROVIDER],
                "Cache-Control": f"max-age={(6 if blocking_request else 0.5)*track.target_duration:.0f}",
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
        self, request: web.Request, stream: Stream, sequence: str
    ) -> web.Response:
        """Return init.mp4."""
        track = stream.add_provider(HLS_PROVIDER)
        if not (segments := track.get_segments()) or not (body := segments[0].init):
            return web.HTTPNotFound()
        return web.Response(
            body=body,
            headers={"Content-Type": "video/mp4"},
        )


class HlsSegmentView(StreamView):
    """Stream view to serve a HLS fmp4 segment."""

    url = r"/api/hls/{token:[a-f0-9]+}/segment/{sequence:\d+}.m4s"
    name = "api:stream:hls:segment"
    cors_allowed = True

    async def handle(
        self, request: web.Request, stream: Stream, sequence: str
    ) -> web.StreamResponse:
        """Handle segments, part segments, and hinted segments."""
        track = stream.add_provider(HLS_PROVIDER)
        track.idle_timer.awake()
        # Ensure that we have a segment. If the request is from a hint for part 0
        # of a segment, there is a small chance it may have arrived before the
        # segment has been put. If this happens, wait for one part and retry.
        if not (
            (segment := track.get_segment(int(sequence)))
            or (
                await track.part_recv(timeout=StreamConstants.HLS_PART_TIMEOUT)
                and (segment := track.get_segment(int(sequence)))
            )
        ):
            return web.Response(
                body=None,
                status=404,
                headers={"Cache-Control": f"max-age={track.target_duration:.0f}"},
            )
        # If the segment is ready or has been hinted, the http_range start should be at most
        # equal to the end of the currently available data.
        # If the segment is complete, the http_range start should be less than the end of the
        # currently available data.
        # If these conditions aren't met then we return a 416.
        # http_range_start can be None, so use a copy that uses 0 instead of None
        if (
            http_start := request.http_range.start or 0
        ) > segment.data_size_without_init or (
            segment.complete and http_start >= segment.data_size_without_init
        ):
            return web.HTTPRequestRangeNotSatisfiable(
                headers={
                    "Cache-Control": f"max-age={track.target_duration:.0f}",
                    "Content-Range": f"bytes */{segment.data_size_without_init}",
                }
            )
        headers = {
            "Content-Type": "video/iso.segment",
            "Cache-Control": f"max-age={6*track.target_duration:.0f}",
        }
        if request.http_range.start is None and request.http_range.stop is None:
            if segment.complete:
                # This is a request for a full segment which is already complete
                # We should return a standard 200 response.
                return web.Response(
                    body=segment.get_bytes_without_init(), headers=headers
                )
            # Otherwise we still return a 200 response, but it is aggregating
            status = 200
        else:
            # For the remaining cases we have a range request.
            # We need to set the Content-Range header
            # See https://datatracker.ietf.org/doc/html/rfc8673#section-2
            if request.http_range.stop is None:
                # This is a special case for establishing current range. We should only
                # get this on a HEAD request. Our clients probably won't send this type
                # of request, but we can try to respond correctly.
                headers[
                    "Content-Range"
                ] = f"bytes {http_start}-{segment.data_size_without_init-1}/*"
                return web.Response(headers=headers, status=206)
            status = 206
            if segment.complete:
                # If the segment is complete we have total size
                headers["Content-Range"] = (
                    f"bytes {http_start}-"
                    + str(
                        min(request.http_range.stop, segment.data_size_without_init) - 1
                    )
                    + f"/{segment.data_size_without_init}"
                )
            else:
                # If we don't have the total size we use a *
                headers[
                    "Content-Range"
                ] = f"bytes {http_start}-{request.http_range.stop-1}/*"
        # Set up streaming response that we can write to as data becomes available
        response = web.StreamResponse(headers=headers, status=status)
        # Waiting until we write to prepare *might* give clients more accurate TTFB
        # and ABR measurements, but it is probably not very useful for us since we
        # only have one rendition anyway. Just prepare here for now.
        await response.prepare(request)
        try:
            for bytes_to_write in segment.get_aggregating_bytes(
                start_loc=http_start, end_loc=request.http_range.stop or float("inf")
            ):
                if bytes_to_write:
                    await response.write(bytes_to_write)
                elif not await track.part_recv(
                    timeout=StreamConstants.HLS_PART_TIMEOUT
                ):
                    break
        except ConnectionResetError:
            _LOGGER.warning("Connection reset while serving HLS partial segment")
        return response
