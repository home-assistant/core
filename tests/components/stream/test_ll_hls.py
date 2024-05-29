"""The tests for hls streams."""

import asyncio
from collections import deque
from http import HTTPStatus
import itertools
import math
import re
from urllib.parse import urlparse

from aiohttp import web
from dateutil import parser
import pytest

from homeassistant.components.stream import create_stream
from homeassistant.components.stream.const import (
    ATTR_SETTINGS,
    CONF_LL_HLS,
    CONF_PART_DURATION,
    CONF_SEGMENT_DURATION,
    DOMAIN,
    HLS_PROVIDER,
)
from homeassistant.components.stream.core import Part
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    FAKE_TIME,
    DefaultSegment as Segment,
    dynamic_stream_settings,
    generate_h264_video,
)
from .test_hls import STREAM_SOURCE, HlsClient, make_playlist

from tests.typing import ClientSessionGenerator

SEGMENT_DURATION = 6
TEST_PART_DURATION = 0.75
NUM_PART_SEGMENTS = int(-(-SEGMENT_DURATION // TEST_PART_DURATION))
PART_INDEPENDENT_PERIOD = int(1 / TEST_PART_DURATION) or 1
BYTERANGE_LENGTH = 1
INIT_BYTES = b"\x00\x00\x00\x08moov"
SEQUENCE_BYTES = bytearray(range(NUM_PART_SEGMENTS * BYTERANGE_LENGTH))
ALT_SEQUENCE_BYTES = bytearray(range(20, 20 + NUM_PART_SEGMENTS * BYTERANGE_LENGTH))
VERY_LARGE_LAST_BYTE_POS = 9007199254740991


@pytest.fixture
def hls_stream(hass: HomeAssistant, hass_client: ClientSessionGenerator):
    """Create test fixture for creating an HLS client for a stream."""

    async def create_client_for_stream(stream):
        stream.ll_hls = True
        http_client = await hass_client()
        parsed_url = urlparse(stream.endpoint_url(HLS_PROVIDER))
        return HlsClient(http_client, parsed_url)

    return create_client_for_stream


def create_segment(sequence):
    """Create an empty segment."""
    segment = Segment(sequence=sequence)
    segment.init = INIT_BYTES
    return segment


def complete_segment(segment):
    """Completes a segment by setting its duration."""
    segment.duration = sum(part.duration for part in segment.parts)


def create_parts(source):
    """Create parts from a source."""
    independent_cycle = itertools.cycle(
        [True] + [False] * (PART_INDEPENDENT_PERIOD - 1)
    )
    return [
        Part(
            duration=TEST_PART_DURATION,
            has_keyframe=next(independent_cycle),
            data=bytes(source[i * BYTERANGE_LENGTH : (i + 1) * BYTERANGE_LENGTH]),
        )
        for i in range(NUM_PART_SEGMENTS)
    ]


def http_range_from_part(part):
    """Return dummy byterange (length, start) given part number."""
    return BYTERANGE_LENGTH, part * BYTERANGE_LENGTH


def make_segment_with_parts(
    segment, num_parts, independent_period, discontinuity=False
):
    """Create a playlist response for a segment including part segments."""
    response = []
    if discontinuity:
        response.append("#EXT-X-DISCONTINUITY")
    response.extend(
        f'#EXT-X-PART:DURATION={TEST_PART_DURATION:.3f},URI="./segment/{segment}.{i}.m4s"{",INDEPENDENT=YES" if i%independent_period==0 else ""}'
        for i in range(num_parts)
    )
    response.extend(
        [
            "#EXT-X-PROGRAM-DATE-TIME:"
            + FAKE_TIME.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z",
            f"#EXTINF:{math.ceil(SEGMENT_DURATION/TEST_PART_DURATION)*TEST_PART_DURATION:.3f},",
            f"./segment/{segment}.m4s",
        ]
    )
    return "\n".join(response)


def make_hint(segment, part):
    """Create a playlist response for the preload hint."""
    return f'#EXT-X-PRELOAD-HINT:TYPE=PART,URI="./segment/{segment}.{part}.m4s"'


async def test_ll_hls_stream(
    hass: HomeAssistant, hls_stream, stream_worker_sync
) -> None:
    """Test hls stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """
    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                # Use a slight mismatch in PART_DURATION to mimic
                # misalignments with source DTSs
                CONF_PART_DURATION: TEST_PART_DURATION - 0.01,
            }
        },
    )

    stream_worker_sync.pause()

    num_playlist_segments = 3
    # Setup demo HLS track
    source = generate_h264_video(duration=num_playlist_segments * SEGMENT_DURATION + 2)
    stream = create_stream(hass, source, {}, dynamic_stream_settings())

    # Request stream
    stream.add_provider(HLS_PROVIDER)
    await stream.start()

    hls_client = await hls_stream(stream)

    # Fetch playlist
    master_playlist_response = await hls_client.get()
    assert master_playlist_response.status == HTTPStatus.OK

    # Fetch init
    master_playlist = await master_playlist_response.text()
    init_response = await hls_client.get("/init.mp4")
    assert init_response.status == HTTPStatus.OK

    # Fetch playlist
    playlist_url = "/" + master_playlist.splitlines()[-1]
    playlist_response = await hls_client.get(
        playlist_url + f"?_HLS_msn={num_playlist_segments-1}"
    )
    assert playlist_response.status == HTTPStatus.OK

    # Fetch segments
    playlist = await playlist_response.text()
    segment_re = re.compile(r"^(?P<segment_url>./segment/\d+\.m4s)")
    for line in playlist.splitlines():
        match = segment_re.match(line)
        if match:
            segment_url = "/" + match.group("segment_url")
            segment_response = await hls_client.get(segment_url)
            assert segment_response.status == HTTPStatus.OK

    def check_part_is_moof_mdat(data: bytes):
        if len(data) < 8 or data[4:8] != b"moof":
            return False
        moof_length = int.from_bytes(data[0:4], byteorder="big")
        if (
            len(data) < moof_length + 8
            or data[moof_length + 4 : moof_length + 8] != b"mdat"
        ):
            return False
        mdat_length = int.from_bytes(
            data[moof_length : moof_length + 4], byteorder="big"
        )
        if mdat_length + moof_length != len(data):
            return False
        return True

    # Parse playlist
    part_re = re.compile(
        r'#EXT-X-PART:DURATION=(?P<part_duration>[0-9]{1,}.[0-9]{3,}),URI="(?P<part_url>.+?)"(,INDEPENDENT=YES)?'
    )
    datetime_re = re.compile(r"#EXT-X-PROGRAM-DATE-TIME:(?P<datetime>.+)")
    inf_re = re.compile(r"#EXTINF:(?P<segment_duration>[0-9]{1,}.[0-9]{3,}),")
    # keep track of which tests were done (indexed by re)
    tested = {regex: False for regex in (part_re, datetime_re, inf_re)}
    # keep track of times and durations along playlist for checking consistency
    part_durations = []
    segment_duration = 0
    datetimes = deque()
    for line in playlist.splitlines():
        match = part_re.match(line)
        if match:
            # Fetch all completed part segments
            part_durations.append(float(match.group("part_duration")))
            part_segment_url = "/" + match.group("part_url")
            part_segment_response = await hls_client.get(
                part_segment_url,
            )
            assert part_segment_response.status == HTTPStatus.OK
            assert check_part_is_moof_mdat(await part_segment_response.read())
            tested[part_re] = True
            continue
        match = datetime_re.match(line)
        if match:
            datetimes.append(parser.parse(match.group("datetime")))
            # Check that segment durations are consistent with PROGRAM-DATE-TIME
            if len(datetimes) > 1:
                datetime_duration = (
                    datetimes[-1] - datetimes.popleft()
                ).total_seconds()
                if segment_duration:
                    assert math.isclose(
                        datetime_duration, segment_duration, rel_tol=1e-3
                    )
                    tested[datetime_re] = True
            continue
        match = inf_re.match(line)
        if match:
            segment_duration = float(match.group("segment_duration"))
            # Check that segment durations are consistent with part durations
            if len(part_durations) > 1:
                assert math.isclose(sum(part_durations), segment_duration, rel_tol=1e-3)
                tested[inf_re] = True
                part_durations.clear()
    # make sure all playlist tests were performed
    assert all(tested.values())

    stream_worker_sync.resume()

    # Stop stream, if it hasn't quit already
    await stream.stop()

    # Ensure playlist not accessible after stream ends
    fail_response = await hls_client.get()
    assert fail_response.status == HTTPStatus.NOT_FOUND


async def test_ll_hls_playlist_view(
    hass: HomeAssistant, hls_stream, stream_worker_sync
) -> None:
    """Test rendering the hls playlist with 1 and 2 output segments."""
    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: TEST_PART_DURATION,
            }
        },
    )

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)

    # Add 2 complete segments to output
    for sequence in range(2):
        segment = create_segment(sequence=sequence)
        hls.put(segment)
        for part in create_parts(SEQUENCE_BYTES):
            segment.async_add_part(part, 0)
            hls.part_put()
        complete_segment(segment)
    await hass.async_block_till_done()

    hls_client = await hls_stream(stream)

    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.OK
    assert await resp.text() == make_playlist(
        sequence=0,
        segments=[
            make_segment_with_parts(i, len(segment.parts), PART_INDEPENDENT_PERIOD)
            for i in range(2)
        ],
        hint=make_hint(2, 0),
        segment_duration=SEGMENT_DURATION,
        part_target_duration=hls.stream_settings.part_target_duration,
    )

    # add one more segment
    segment = create_segment(sequence=2)
    hls.put(segment)
    for part in create_parts(SEQUENCE_BYTES):
        segment.async_add_part(part, 0)
        hls.part_put()
    complete_segment(segment)

    await hass.async_block_till_done()
    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.OK
    assert await resp.text() == make_playlist(
        sequence=0,
        segments=[
            make_segment_with_parts(i, len(segment.parts), PART_INDEPENDENT_PERIOD)
            for i in range(3)
        ],
        hint=make_hint(3, 0),
        segment_duration=SEGMENT_DURATION,
        part_target_duration=hls.stream_settings.part_target_duration,
    )

    stream_worker_sync.resume()
    await stream.stop()


async def test_ll_hls_msn(
    hass: HomeAssistant, hls_stream, stream_worker_sync, hls_sync
) -> None:
    """Test that requests using _HLS_msn get held and returned or rejected."""
    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: TEST_PART_DURATION,
            }
        },
    )

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()

    hls = stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    # Create 4 requests for sequences 0 through 3
    # 0 and 1 should hold then go through and 2 and 3 should fail immediately.

    hls_sync.reset_request_pool(4)
    msn_requests = asyncio.gather(
        *(hls_client.get(f"/playlist.m3u8?_HLS_msn={i}") for i in range(4))
    )

    for sequence in range(3):
        await hls_sync.wait_for_handler()
        segment = Segment(sequence=sequence, duration=SEGMENT_DURATION)
        hls.put(segment)

    msn_responses = await msn_requests

    assert msn_responses[0].status == HTTPStatus.OK
    assert msn_responses[1].status == HTTPStatus.OK
    assert msn_responses[2].status == HTTPStatus.BAD_REQUEST
    assert msn_responses[3].status == HTTPStatus.BAD_REQUEST

    # Sequence number is now 2. Create six more requests for sequences 0 through 5.
    # Calls for msn 0 through 4 should work, 5 should fail.

    hls_sync.reset_request_pool(6)
    msn_requests = asyncio.gather(
        *(hls_client.get(f"/playlist.m3u8?_HLS_msn={i}") for i in range(6))
    )
    for sequence in range(3, 6):
        await hls_sync.wait_for_handler()
        segment = Segment(sequence=sequence, duration=SEGMENT_DURATION)
        hls.put(segment)

    msn_responses = await msn_requests
    assert msn_responses[0].status == HTTPStatus.OK
    assert msn_responses[1].status == HTTPStatus.OK
    assert msn_responses[2].status == HTTPStatus.OK
    assert msn_responses[3].status == HTTPStatus.OK
    assert msn_responses[4].status == HTTPStatus.OK
    assert msn_responses[5].status == HTTPStatus.BAD_REQUEST

    stream_worker_sync.resume()


async def test_ll_hls_playlist_bad_msn_part(
    hass: HomeAssistant, hls_stream, stream_worker_sync
) -> None:
    """Test some playlist requests with invalid _HLS_msn/_HLS_part."""

    async def _handler_bad_request(request):
        raise web.HTTPBadRequest

    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: TEST_PART_DURATION,
            }
        },
    )

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()

    hls = stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    # All GET calls to '/.../playlist.m3u8' should raise a HTTPBadRequest exception
    hls_client.http_client.app.router._frozen = False
    parsed_url = urlparse(stream.endpoint_url(HLS_PROVIDER))
    url = "/".join(parsed_url.path.split("/")[:-1]) + "/playlist.m3u8"
    hls_client.http_client.app.router.add_route("GET", url, _handler_bad_request)

    # If the Playlist URI contains an _HLS_part directive but no _HLS_msn
    # directive, the Server MUST return Bad Request, such as HTTP 400.

    assert (
        await hls_client.get("/playlist.m3u8?_HLS_part=1")
    ).status == HTTPStatus.BAD_REQUEST

    # Seed hls with 1 complete segment and 1 in process segment
    segment = create_segment(sequence=0)
    hls.put(segment)
    for part in create_parts(SEQUENCE_BYTES):
        segment.async_add_part(part, 0)
        hls.part_put()
    complete_segment(segment)

    segment = create_segment(sequence=1)
    hls.put(segment)
    remaining_parts = create_parts(SEQUENCE_BYTES)
    num_completed_parts = len(remaining_parts) // 2
    for part in remaining_parts[:num_completed_parts]:
        segment.async_add_part(part, 0)

    # If the _HLS_msn is greater than the Media Sequence Number of the last
    # Media Segment in the current Playlist plus two, or if the _HLS_part
    # exceeds the last Partial Segment in the current Playlist by the
    # Advance Part Limit, then the server SHOULD immediately return Bad
    # Request, such as HTTP 400.  The Advance Part Limit is three divided
    # by the Part Target Duration if the Part Target Duration is less than
    # one second, or three otherwise.

    # Current sequence number is 1 and part number is num_completed_parts-1
    # The following two tests should fail immediately:
    # - request with a _HLS_msn of 4
    # - request with a _HLS_msn of 1 and a _HLS_part of num_completed_parts-1+advance_part_limit
    assert (
        await hls_client.get("/playlist.m3u8?_HLS_msn=4")
    ).status == HTTPStatus.BAD_REQUEST
    assert (
        await hls_client.get(
            f"/playlist.m3u8?_HLS_msn=1&_HLS_part={num_completed_parts-1+hass.data[DOMAIN][ATTR_SETTINGS].hls_advance_part_limit}"
        )
    ).status == HTTPStatus.BAD_REQUEST
    stream_worker_sync.resume()


async def test_ll_hls_playlist_rollover_part(
    hass: HomeAssistant, hls_stream, stream_worker_sync, hls_sync
) -> None:
    """Test playlist request rollover."""

    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: TEST_PART_DURATION,
            }
        },
    )

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()

    hls = stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    # Seed hls with 1 complete segment and 1 in process segment
    for sequence in range(2):
        segment = create_segment(sequence=sequence)
        hls.put(segment)

        for part in create_parts(SEQUENCE_BYTES):
            segment.async_add_part(part, 0)
            hls.part_put()
        complete_segment(segment)

    await hass.async_block_till_done()

    hls_sync.reset_request_pool(4)
    segment = hls.get_segment(1)
    # the first request corresponds to the last part of segment 1
    # the remaining requests correspond to part 0 of segment 2
    requests = asyncio.gather(
        *(
            [
                hls_client.get(
                    f"/playlist.m3u8?_HLS_msn=1&_HLS_part={len(segment.parts)-1}"
                ),
                hls_client.get(
                    f"/playlist.m3u8?_HLS_msn=1&_HLS_part={len(segment.parts)}"
                ),
                hls_client.get(
                    f"/playlist.m3u8?_HLS_msn=1&_HLS_part={len(segment.parts)+1}"
                ),
                hls_client.get("/playlist.m3u8?_HLS_msn=2&_HLS_part=0"),
            ]
        )
    )

    await hls_sync.wait_for_handler()

    segment = create_segment(sequence=2)
    hls.put(segment)
    await hass.async_block_till_done()

    remaining_parts = create_parts(SEQUENCE_BYTES)
    segment.async_add_part(remaining_parts.pop(0), 0)
    hls.part_put()

    await hls_sync.wait_for_handler()

    different_response, *same_responses = await requests

    assert different_response.status == HTTPStatus.OK
    assert all(response.status == HTTPStatus.OK for response in same_responses)
    different_playlist = await different_response.read()
    same_playlists = [await response.read() for response in same_responses]
    assert different_playlist != same_playlists[0]
    assert all(playlist == same_playlists[0] for playlist in same_playlists[1:])

    stream_worker_sync.resume()


async def test_ll_hls_playlist_msn_part(
    hass: HomeAssistant, hls_stream, stream_worker_sync, hls_sync
) -> None:
    """Test that requests using _HLS_msn and _HLS_part get held and returned."""

    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: TEST_PART_DURATION,
            }
        },
    )

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()

    hls = stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    # Seed hls with 1 complete segment and 1 in process segment
    segment = create_segment(sequence=0)
    hls.put(segment)
    for part in create_parts(SEQUENCE_BYTES):
        segment.async_add_part(part, 0)
        hls.part_put()
    complete_segment(segment)

    segment = create_segment(sequence=1)
    hls.put(segment)
    remaining_parts = create_parts(SEQUENCE_BYTES)
    num_completed_parts = len(remaining_parts) // 2
    for part in remaining_parts[:num_completed_parts]:
        segment.async_add_part(part, 0)
    del remaining_parts[:num_completed_parts]

    # Make requests for all the part segments up to n+ADVANCE_PART_LIMIT
    hls_sync.reset_request_pool(
        num_completed_parts
        + int(-(-hass.data[DOMAIN][ATTR_SETTINGS].hls_advance_part_limit // 1))
    )
    msn_requests = asyncio.gather(
        *(
            hls_client.get(f"/playlist.m3u8?_HLS_msn=1&_HLS_part={i}")
            for i in range(
                num_completed_parts
                + int(-(-hass.data[DOMAIN][ATTR_SETTINGS].hls_advance_part_limit // 1))
            )
        )
    )

    while remaining_parts:
        await hls_sync.wait_for_handler()
        segment.async_add_part(remaining_parts.pop(0), 0)
        hls.part_put()

    msn_responses = await msn_requests

    # All the responses should succeed except the last one which fails
    assert all(response.status == HTTPStatus.OK for response in msn_responses[:-1])
    assert msn_responses[-1].status == HTTPStatus.BAD_REQUEST

    stream_worker_sync.resume()


async def test_get_part_segments(
    hass: HomeAssistant, hls_stream, stream_worker_sync, hls_sync
) -> None:
    """Test requests for part segments and hinted parts."""
    await async_setup_component(
        hass,
        "stream",
        {
            "stream": {
                CONF_LL_HLS: True,
                CONF_SEGMENT_DURATION: SEGMENT_DURATION,
                CONF_PART_DURATION: TEST_PART_DURATION,
            }
        },
    )

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()

    hls = stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    # Seed hls with 1 complete segment and 1 in process segment
    segment = create_segment(sequence=0)
    hls.put(segment)
    for part in create_parts(SEQUENCE_BYTES):
        segment.async_add_part(part, 0)
        hls.part_put()
    complete_segment(segment)

    segment = create_segment(sequence=1)
    hls.put(segment)
    remaining_parts = create_parts(SEQUENCE_BYTES)
    num_completed_parts = len(remaining_parts) // 2
    for _ in range(num_completed_parts):
        segment.async_add_part(remaining_parts.pop(0), 0)

    # Make requests for all the existing part segments
    # These should succeed
    requests = asyncio.gather(
        *(
            hls_client.get(f"/segment/1.{part}.m4s")
            for part in range(num_completed_parts)
        )
    )
    responses = await requests
    assert all(response.status == HTTPStatus.OK for response in responses)
    assert all(
        [
            await responses[i].read() == segment.parts[i].data
            for i in range(len(responses))
        ]
    )

    # Request for next segment which has not yet been hinted (we will only hint
    # for this segment after segment 1 is complete).
    # This should fail, but it will hold for one more part_put before failing.
    hls_sync.reset_request_pool(1)
    request = asyncio.create_task(hls_client.get("/segment/2.0.m4s"))
    await hls_sync.wait_for_handler()
    hls.part_put()
    response = await request
    assert response.status == HTTPStatus.NOT_FOUND

    # Put the remaining parts and complete the segment
    while remaining_parts:
        await hls_sync.wait_for_handler()
        # Put one more part segment
        segment.async_add_part(remaining_parts.pop(0), 0)
        hls.part_put()
    complete_segment(segment)

    # Now the hint should have moved to segment 2
    # The request for segment 2 which failed before should work now
    hls_sync.reset_request_pool(1)
    request = asyncio.create_task(hls_client.get("/segment/2.0.m4s"))
    # Put an entire segment and its parts.
    segment = create_segment(sequence=2)
    hls.put(segment)
    remaining_parts = create_parts(ALT_SEQUENCE_BYTES)
    for part in remaining_parts:
        await hls_sync.wait_for_handler()
        segment.async_add_part(part, 0)
        hls.part_put()
    complete_segment(segment)
    # Check the response
    response = await request
    assert response.status == HTTPStatus.OK
    assert (
        await response.read()
        == ALT_SEQUENCE_BYTES[: len(hls.get_segment(2).parts[0].data)]
    )

    stream_worker_sync.resume()
