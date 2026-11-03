"""Tests for the dedicated HKSV shared stream output."""

# Tests exercise internal stream muxing and timing behavior.
# pylint: disable=home-assistant-component-root-import

import asyncio
from fractions import Fraction
from io import BytesIO
from itertools import pairwise
from pathlib import Path
import shutil
import subprocess
from threading import Event
from unittest.mock import AsyncMock, Mock, patch

import av
import pytest

from homeassistant.components.homekit.hksv_stream import (
    HKSVStreamOutput,
    SharedCameraStream,
    inspect_recording,
)
from homeassistant.components.stream.core import StreamSettings
from homeassistant.components.stream.diagnostics import Diagnostics
from homeassistant.components.stream.worker import (
    AudioTimestampNormalizer,
    StreamEndedError,
    StreamState,
    stream_worker,
)


def segment(
    stream_id: int, sequence: int, *, complete: bool = True, keyframe: bool = True
):
    """Create a minimal segment."""
    return Mock(
        stream_id=stream_id,
        sequence=sequence,
        init=b"init",
        duration=1.0,
        data_size=8,
        complete=complete,
        parts=[Mock(has_keyframe=keyframe)],
        get_data=Mock(return_value=b"fragment"),
    )


async def test_snapshot_only_current_complete_keyframe_segments() -> None:
    """Do not mix generations or hand off incomplete/non-keyframe fragments."""
    output = Mock()
    output.get_segments.return_value = [
        segment(1, 1),
        segment(2, 2),
        segment(2, 3, complete=False),
        segment(2, 4, keyframe=False),
    ]
    shared = SharedCameraStream(Mock(), output)
    fragments = shared.snapshot()
    assert [(f.stream_id, f.sequence, f.data) for f in fragments] == [
        (2, 2, b"fragment")
    ]


async def test_snapshot_partial_is_explicit_and_generation_bounded() -> None:
    """Native inspection can see an incomplete current segment without changing recording."""
    output = Mock()
    output.get_segments.return_value = [
        segment(1, 1),
        segment(2, 2),
        segment(2, 3, complete=False),
    ]
    shared = SharedCameraStream(Mock(), output)
    assert [item.sequence for item in shared.snapshot()] == [2]
    assert [item.sequence for item in shared.snapshot(include_partial=True)] == [2, 3]


async def test_close_only_own_output() -> None:
    """Closing the adapter detaches its own output once."""
    output = Mock()
    stream = Mock()
    stream.outputs.return_value = {"homekit_secure_video": output, "hls": Mock()}
    stream.remove_provider = AsyncMock()
    shared = SharedCameraStream(stream, output)
    await shared.close()
    await shared.close()
    stream.remove_provider.assert_awaited_once_with(output)


async def test_iterator_observes_generation_change() -> None:
    """A restart surfaces a new initialization generation."""
    output = Mock()
    output.get_segments.side_effect = [[segment(1, 1)], [segment(2, 1)]]
    output.part_recv = AsyncMock(return_value=True)
    shared = SharedCameraStream(Mock(), output)
    iterator = shared.fragments()
    assert (await anext(iterator)).stream_id == 1
    assert (await anext(iterator)).stream_id == 2
    await iterator.aclose()


def test_media_inspection_of_real_fragmented_mp4(tmp_path: Path) -> None:
    """Inspect real H.264/AAC media and reject a truncated sample."""
    if not (ffmpeg := shutil.which("ffmpeg")):
        pytest.skip("ffmpeg unavailable")
    path = tmp_path / "sample.mp4"
    process = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=15",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=24000",
            "-t",
            "5",
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "30",
            "-c:a",
            "aac",
            "-ac",
            "1",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            "-f",
            "mp4",
            "-y",
            str(path),
        ],
        capture_output=True,
        check=False,
    )
    if process.returncode:
        pytest.skip("ffmpeg does not support test encoders")
    media = path.read_bytes()
    observation = inspect_recording(b"", (media,))
    assert (observation.video_codec, observation.width, observation.height) == (
        "h264",
        320,
        240,
    )
    assert (
        observation.audio_codec,
        observation.audio_rate,
        observation.audio_channels,
    ) == ("aac", 24000, 1)
    assert observation.h264_profile_idc == 66
    assert observation.peak_fps == 15
    assert 1.5 < observation.max_keyframe_interval < 2.5
    with pytest.raises((ValueError, av.error.InvalidDataError)):  # pylint: disable=c-extension-no-member
        inspect_recording(b"", (media[:100],))


async def test_slow_consumer_rejects_missing_segment() -> None:
    """A consumer must not silently write discontinuous fMP4."""
    output = Mock()
    output.get_segments.side_effect = [[segment(1, 1)], [segment(1, 3)]]
    output.part_recv = AsyncMock(return_value=True)
    iterator = SharedCameraStream(Mock(), output).fragments()
    assert (await anext(iterator)).sequence == 1
    with pytest.raises(ValueError, match="missed"):
        await anext(iterator)


def test_oversized_segment_is_not_copied() -> None:
    """An oversized buffer fails before allocating segment copies."""
    large = segment(1, 1)
    large.data_size = 16 * 1024 * 1024
    output = Mock()
    output.get_segments.return_value = [large]
    with pytest.raises(ValueError, match="byte limit"):
        SharedCameraStream(Mock(), output).snapshot()
    large.get_data.assert_not_called()


def test_shared_worker_transcodes_alaw_only_when_requested(tmp_path: Path) -> None:
    """A real source retains audio with HKSV and retains old behavior otherwise."""
    if not (ffmpeg := shutil.which("ffmpeg")):
        pytest.skip("ffmpeg unavailable")
    path = tmp_path / "source.mkv"
    process = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=15",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=8000",
            "-t",
            "20",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "30",
            "-c:a",
            "pcm_alaw",
            "-f",
            "matroska",
            "-y",
            str(path),
        ],
        capture_output=True,
        check=False,
    )
    if process.returncode:
        pytest.skip("ffmpeg does not support test encoders")

    for requested in (False, True):

        class Output:
            requires_aac_audio = requested

            def __init__(self) -> None:
                self.segments = []

            def put(self, segment):
                self.segments.append(segment)

            def part_put(self):
                pass

        output = Output()
        hass = Mock()
        hass.loop.call_soon_threadsafe.side_effect = lambda callback, *args: callback(
            *args
        )
        state = StreamState(hass, lambda output=output: {"test": output}, Diagnostics())
        settings = StreamSettings(False, 1.5, 2, 3, 2)
        with pytest.raises(StreamEndedError):
            stream_worker(str(path), {}, settings, state, Mock(), Event())
        segments = [segment for segment in output.segments if segment.complete]
        assert len(segments) >= 3
        # A live consumer pipes one initialization followed by low-latency parts.
        pipe_data = segments[0].init + b"".join(
            part.data for segment in segments for part in segment.parts
        )
        piped = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-f",
                "null",
                "-",
            ],
            input=pipe_data,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert piped.returncode == 0
        if requested:
            opus = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-map",
                    "0:a:0",
                    "-c:a",
                    "libopus",
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    "-f",
                    "opus",
                    "pipe:1",
                ],
                input=pipe_data,
                capture_output=True,
                check=False,
                timeout=10,
            )
            assert opus.returncode == 0
            with av.open(BytesIO(opus.stdout), format="ogg") as audio:
                assert audio.streams.audio[0].codec_context.name == "opus"
            dual = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-map",
                    "0:v:0",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-tune",
                    "zerolatency",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "15",
                    "-payload_type",
                    "99",
                    "-f",
                    "rtp",
                    "-srtp_out_suite",
                    "AES_CM_128_HMAC_SHA1_80",
                    "-srtp_out_params",
                    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    "srtp://127.0.0.1:45520?pkt_size=1316",
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-c:a",
                    "libopus",
                    "-application",
                    "lowdelay",
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    "-b:a",
                    "24k",
                    "-bufsize",
                    "96k",
                    "-frame_duration",
                    "20",
                    "-payload_type",
                    "110",
                    "-f",
                    "rtp",
                    "rtp://127.0.0.1:45522?pkt_size=188",
                ],
                input=pipe_data,
                capture_output=True,
                check=False,
                timeout=20,
            )
            assert dual.returncode == 0, dual.stderr.decode(errors="replace")
        for segment in segments:
            with av.open(
                BytesIO(segment.init + segment.get_data()), format="mp4"
            ) as container:
                assert container.streams.video[0].codec_context.name == "h264"
                assert [
                    stream.codec_context.name for stream in container.streams.audio
                ] == (["aac"] if requested else [])
                packets = [
                    packet for packet in container.demux() if packet.dts is not None
                ]
                if requested:
                    video_times = [
                        float(packet.dts * packet.time_base)
                        for packet in packets
                        if packet.stream.type == "video"
                    ]
                    audio_times = [
                        float(packet.dts * packet.time_base)
                        for packet in packets
                        if packet.stream.type == "audio"
                    ]
                    assert video_times and audio_times
                    assert abs(video_times[0] - audio_times[0]) < 0.3
                    assert abs(video_times[-1] - audio_times[-1]) < 0.3


def test_audio_timestamps_clamp_overlap_and_preserve_gap() -> None:
    """Real camera overlap is repaired without discarding forward gaps."""
    clock = AudioTimestampNormalizer()
    actual = []
    for pts in (3130, 4154, 4170, 5194, 10000):
        frame = av.AudioFrame(format="s16", layout="mono", samples=1024)
        frame.sample_rate = 8000
        frame.time_base = Fraction(1, 8000)
        frame.pts = pts
        clock.normalize(frame)
        actual.append(frame.pts)
    assert actual == [3130, 4154, 5178, 6202, 10000]


def test_audio_timestamp_normalization_resamples_and_muxes_aac() -> None:
    """Real overlapping source PTS become ordered AAC frames in an MP4."""
    clock = AudioTimestampNormalizer()
    resampler = av.audio.resampler.AudioResampler(  # pylint: disable=c-extension-no-member
        format="fltp", layout="mono", rate=24000
    )
    output = BytesIO()
    container = av.open(output, mode="w", format="mp4")
    stream = container.add_stream("aac", rate=24000)
    stream.layout = "mono"
    converted_frames = []
    for pts in (3130, 4154, 4170, 5194):
        frame = av.AudioFrame(format="s16", layout="mono", samples=1024)
        frame.sample_rate = 8000
        frame.time_base = Fraction(1, 8000)
        frame.pts = pts
        clock.normalize(frame)
        converted_frames.extend(resampler.resample(frame))
    converted_frames.extend(resampler.resample(None))
    for previous, current in pairwise(converted_frames):
        assert previous.pts is not None and current.pts is not None
        assert current.pts >= previous.pts + previous.samples
    for frame in converted_frames:
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()
    output.seek(0)
    with av.open(output, format="mp4") as result:
        assert result.streams.audio[0].codec_context.name == "aac"
        assert sum(1 for packet in result.demux(audio=0) if packet.dts is not None) > 0


async def test_shared_provider_is_reference_counted() -> None:
    """Independent clients share one provider and release only their own lease."""
    hass = Mock()
    hass.data = {}
    output = Mock()
    stream = Mock()
    stream.outputs.return_value = {"homekit_secure_video": output}
    stream.remove_provider = AsyncMock()
    owner = SharedCameraStream(stream, output)
    with patch.object(
        SharedCameraStream, "_open_owned", new_callable=AsyncMock, return_value=owner
    ) as opener:
        first, second, third = await asyncio.gather(
            SharedCameraStream.open(hass, "camera.example"),
            SharedCameraStream.open(hass, "camera.example"),
            SharedCameraStream.open(hass, "camera.example"),
        )
        opener.assert_awaited_once()
        await first.close()
        await second.close()
        stream.remove_provider.assert_not_awaited()
        await third.close()
        stream.remove_provider.assert_awaited_once_with(output)


async def test_live_parts_start_at_keyframe_and_detect_generation_change() -> None:
    """Each live reader receives low-latency parts and rejects discontinuities."""
    output = Mock()
    output.idle_timer = Mock()
    output.part_recv = AsyncMock()
    part0 = Mock(has_keyframe=True, data=b"part0")
    part1 = Mock(has_keyframe=False, data=b"part1")
    current = Mock(
        stream_id=1, sequence=8, init=b"init", parts=[part0, part1], complete=False
    )
    output.get_segments.return_value = [current]
    shared = SharedCameraStream(Mock(), output)
    reader = shared.live_parts()
    assert await anext(reader) == b"init"
    assert await anext(reader) == b"part0"
    assert await anext(reader) == b"part1"
    output.get_segments.return_value = [Mock(stream_id=2)]
    with pytest.raises(ValueError, match="generation changed"):
        await anext(reader)
    await reader.aclose()


async def test_live_parts_sees_next_segment_published_during_yield() -> None:
    """Do not wait for another notification when the next segment already exists."""
    output = Mock()
    output.idle_timer = Mock()
    event = asyncio.Event()
    output.part_recv = event.wait
    current = Mock(
        stream_id=1,
        sequence=8,
        init=b"init",
        parts=[Mock(has_keyframe=True, data=b"part0")],
        complete=False,
    )
    following = Mock(
        stream_id=1,
        sequence=9,
        init=b"init",
        parts=[Mock(has_keyframe=True, data=b"part1")],
        complete=False,
    )
    output.get_segments.return_value = [current]
    reader = SharedCameraStream(Mock(), output).live_parts()
    assert await anext(reader) == b"init"
    assert await anext(reader) == b"part0"
    # Publication occurs while the consumer is processing the yielded part.
    current.complete = True
    output.get_segments.return_value = [current, following]
    event.set()
    event.clear()
    try:
        async with asyncio.timeout(0.1):
            assert await anext(reader) == b"part1"
    finally:
        await reader.aclose()


async def test_live_preparation_pins_measured_segment() -> None:
    """Catch up the measured segment even if another segment appears later."""
    output = Mock()
    output.idle_timer = Mock()
    output.stream_settings.part_target_duration = 1.0
    old = Mock(
        stream_id=1,
        sequence=8,
        init=b"old init",
        complete=True,
        parts=[Mock(has_keyframe=True, data=b"old part")],
    )
    new = Mock(
        stream_id=1,
        sequence=9,
        init=b"new init",
        complete=False,
        parts=[Mock(has_keyframe=True, data=b"new part")],
    )
    output.get_segments.return_value = [old]
    shared = SharedCameraStream(Mock(), output)
    with patch(
        "homeassistant.components.homekit.hksv_stream.inspect_recording"
    ) as inspect:
        inspect.return_value.observation_seconds = 8.0
        assert await shared.prepare_live_input() == 6.0
        inspect.assert_called_once_with(b"old init", (b"old part",), False)
    output.get_segments.return_value = [old, new]
    reader = shared.live_parts()
    assert await anext(reader) == b"old init"
    assert await anext(reader) == b"old part"
    assert await anext(reader) == b"new part"
    await reader.aclose()


async def test_live_preparation_rejects_replaced_generation() -> None:
    """A pinned start does not silently switch after a source restart."""
    output = Mock()
    output.idle_timer = Mock()
    output.stream_settings.part_target_duration = 1.0
    old = Mock(
        stream_id=1,
        sequence=8,
        init=b"init",
        parts=[Mock(has_keyframe=True, data=b"part")],
    )
    output.get_segments.return_value = [old]
    shared = SharedCameraStream(Mock(), output)
    with patch(
        "homeassistant.components.homekit.hksv_stream.inspect_recording"
    ) as inspect:
        inspect.return_value.observation_seconds = 5.0
        assert await shared.prepare_live_input() == 3.0
    output.get_segments.return_value = [Mock(stream_id=2, sequence=9)]
    reader = shared.live_parts()
    with pytest.raises(ValueError, match="Pinned live segment"):
        await anext(reader)
    await reader.aclose()


@pytest.mark.parametrize("invalid", [False, True])
async def test_live_preparation_without_measurable_media(invalid: bool) -> None:
    """No buffered segment or invalid media grants no catch-up credit."""
    output = Mock()
    output.idle_timer = Mock()
    output.get_segments.return_value = (
        [
            Mock(
                stream_id=1,
                sequence=1,
                init=b"init",
                parts=[Mock(has_keyframe=True, data=b"invalid")],
            )
        ]
        if invalid
        else []
    )
    shared = SharedCameraStream(Mock(), output)
    with patch(
        "homeassistant.components.homekit.hksv_stream.inspect_recording",
        side_effect=ValueError,
    ):
        assert await shared.prepare_live_input() == 0


async def test_shared_snapshot_does_not_add_hls_provider() -> None:
    """A snapshot uses the keyframe converter on its already-owned stream."""
    stream = Mock()
    stream.async_get_image = AsyncMock(return_value=b"jpeg")
    shared = SharedCameraStream(stream, Mock())
    assert await shared.image(640, 360) == b"jpeg"
    stream.async_get_image.assert_awaited_once_with(
        width=640,
        height=360,
        wait_for_next_keyframe=True,
        use_existing_stream=True,
        require_fresh=True,
    )
    stream.add_provider.assert_not_called()


async def test_cancelled_lease_close_finishes_after_lock_released() -> None:
    """Cancelling a caller waiting for the lock cannot leak its provider lease."""
    hass = Mock()
    hass.data = {}
    output = Mock()
    stream = Mock()
    stream.outputs.return_value = {"homekit_secure_video": output}
    stream.remove_provider = AsyncMock()
    owner = SharedCameraStream(stream, output)
    with patch.object(
        SharedCameraStream, "_open_owned", new_callable=AsyncMock, return_value=owner
    ):
        lease = await SharedCameraStream.open(hass, "camera.test")
        entry = lease._shared_entry
        await entry.lock.acquire()
        closing = asyncio.create_task(lease.close())
        await asyncio.sleep(0)
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        entry.lock.release()
        await lease.close()
        assert entry.references == 0
        stream.remove_provider.assert_awaited_once_with(output)


async def test_cancelled_last_close_finishes_provider_removal() -> None:
    """Cancellation during provider removal cannot orphan its output."""
    hass = Mock()
    hass.data = {}
    output = Mock()
    stream = Mock()
    stream.outputs.return_value = {"homekit_secure_video": output}
    entered = asyncio.Event()
    proceed = asyncio.Event()

    async def remove(_output):
        entered.set()
        await proceed.wait()

    stream.remove_provider = AsyncMock(side_effect=remove)
    owner = SharedCameraStream(stream, output)
    with patch.object(
        SharedCameraStream, "_open_owned", new_callable=AsyncMock, return_value=owner
    ):
        lease = await SharedCameraStream.open(hass, "camera.test")
        closing = asyncio.create_task(lease.close())
        await entered.wait()
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        proceed.set()
        await lease.close()
        assert lease._shared_entry.owner is None
        stream.remove_provider.assert_awaited_once_with(output)


async def test_detached_provider_is_recreated_for_new_lease() -> None:
    """An output removed by the worker is never reused by a new consumer."""
    hass = Mock()
    hass.data = {}
    old_output, new_output = Mock(), Mock()
    stream = Mock()
    outputs = {"homekit_secure_video": old_output}
    stream.outputs.side_effect = lambda: outputs
    stream.remove_provider = AsyncMock()
    old_owner, new_owner = (
        SharedCameraStream(stream, old_output),
        SharedCameraStream(stream, new_output),
    )
    with patch.object(
        SharedCameraStream,
        "_open_owned",
        new_callable=AsyncMock,
        side_effect=[old_owner, new_owner],
    ) as opener:
        old_lease = await SharedCameraStream.open(hass, "camera.test")
        outputs["homekit_secure_video"] = new_output
        new_lease = await SharedCameraStream.open(hass, "camera.test")
        assert opener.await_count == 2
        with pytest.raises(ValueError, match="no longer attached"):
            old_lease.snapshot()
        await old_lease.close()
        stream.remove_provider.assert_not_awaited()
        await new_lease.close()
        stream.remove_provider.assert_awaited_once_with(new_output)


async def test_open_waiting_for_last_close_keeps_one_registry_entry() -> None:
    """An opener waiting for removal cannot race into a second owner."""
    hass = Mock()
    hass.data = {}
    stream = Mock()
    output_a, output_b = Mock(), Mock()
    outputs = {"homekit_secure_video": output_a}
    stream.outputs.side_effect = outputs.copy
    entered, proceed = asyncio.Event(), asyncio.Event()

    async def remove(output):
        if output is output_a:
            entered.set()
            await proceed.wait()
        outputs.pop("homekit_secure_video", None)

    stream.remove_provider = AsyncMock(side_effect=remove)
    first_owner, second_owner = (
        SharedCameraStream(stream, output_a),
        SharedCameraStream(stream, output_b),
    )

    async def create(*_args, **_kwargs):
        if not outputs:
            outputs["homekit_secure_video"] = output_b
            return second_owner
        return first_owner

    with patch.object(SharedCameraStream, "_open_owned", side_effect=create):
        first = await SharedCameraStream.open(hass, "camera.test")
        closing = asyncio.create_task(first.close())
        await entered.wait()
        opening = asyncio.create_task(SharedCameraStream.open(hass, "camera.test"))
        await asyncio.sleep(0)
        proceed.set()
        second = await opening
        await closing
        assert len(hass.data["homekit_shared_camera_streams"]) == 1
        await second.close()
        assert not hass.data["homekit_shared_camera_streams"]


async def test_preloaded_worker_restarts_for_shared_audio() -> None:
    """A running preloaded worker needs audio activation even without outputs."""
    hass = Mock()
    hass.data = {}
    stream = Mock()
    stream.is_running = True
    stream.outputs.return_value = {}
    stream.start = AsyncMock()
    output = Mock(spec=HKSVStreamOutput)
    stream.add_provider.return_value = output
    camera = Mock(async_create_stream=AsyncMock(return_value=stream))
    with patch(
        "homeassistant.components.homekit.hksv_stream.get_camera_from_entity_id",
        return_value=camera,
    ):
        lease = await SharedCameraStream.open(hass, "camera.preloaded")
    stream.update_source.assert_called_once_with(stream.source)
    assert output.requires_aac_audio
    await lease.close()


def test_follow_live_start_pins_same_output() -> None:
    """Audio and video leases share the same cursor and initial catch-up."""
    output = Mock()
    video = SharedCameraStream(Mock(), output)
    audio = SharedCameraStream(Mock(), output)
    video._live_start = (3, 42)
    video.live_initial_burst = 4.5
    assert audio.follow_live_start(video)
    assert audio._live_start == (3, 42)
    assert audio.live_initial_burst == 4.5
    assert not SharedCameraStream(Mock(), Mock()).follow_live_start(video)


async def test_shared_clock_policy_conflict_and_release() -> None:
    """Sharing requires the same clock policy and the last release restores it."""
    hass = Mock()
    hass.data = {}
    output = Mock()
    output.requires_wallclock_timestamps = True
    other = Mock()
    other.requires_wallclock_timestamps = False
    stream = Mock()
    stream.pyav_options = {}
    stream.is_running = True
    stream.outputs.return_value = {"homekit_secure_video": output, "hls": other}

    async def remove(_output: HKSVStreamOutput) -> None:
        stream.outputs.return_value = {"hls": other}

    stream.remove_provider = AsyncMock(side_effect=remove)
    owner = SharedCameraStream(stream, output)
    with patch.object(
        SharedCameraStream, "_open_owned", new_callable=AsyncMock, return_value=owner
    ):
        first = await SharedCameraStream.open(
            hass, "camera.test", receive_timestamps=True
        )
        second = await SharedCameraStream.open(
            hass, "camera.test", receive_timestamps=True
        )
        with pytest.raises(ValueError, match="Conflicting camera timestamp"):
            await SharedCameraStream.open(hass, "camera.test")
        await first.close()
        stream.update_source.assert_not_called()
        await second.close()
        stream.update_source.assert_called_once_with(stream.source)


async def test_clock_release_preserves_explicit_camera_option() -> None:
    """Removing an HKSV output does not change an existing camera clock option."""
    output = Mock()
    output.requires_wallclock_timestamps = True
    other = Mock()
    stream = Mock()
    stream.pyav_options = {"use_wallclock_as_timestamps": "1"}
    stream.is_running = True
    stream.outputs.return_value = {"homekit_secure_video": output, "hls": other}
    stream.remove_provider = AsyncMock()
    await SharedCameraStream(stream, output).close()
    stream.update_source.assert_not_called()


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_clock_start_failure_restores_remaining_stream(
    failure: type[BaseException],
) -> None:
    """Failure while starting HKSV restores the remaining provider clock policy."""
    hass = Mock()
    hass.data = {}
    stream = Mock()
    stream.is_running = True
    stream.pyav_options = {}
    output = Mock(spec=HKSVStreamOutput)
    other = Mock()
    other.requires_wallclock_timestamps = False
    outputs = {"hls": other}
    stream.outputs.side_effect = outputs.copy

    def add_provider(_name: str, *, timeout: int) -> HKSVStreamOutput:
        outputs["homekit_secure_video"] = output
        return output

    async def remove_provider(_output: HKSVStreamOutput) -> None:
        del outputs["homekit_secure_video"]

    stream.add_provider.side_effect = add_provider
    stream.remove_provider = AsyncMock(side_effect=remove_provider)
    stream.start = AsyncMock(side_effect=failure)
    camera = Mock(async_create_stream=AsyncMock(return_value=stream))
    with (
        patch(
            "homeassistant.components.homekit.hksv_stream.get_camera_from_entity_id",
            return_value=camera,
        ),
        pytest.raises(failure),
    ):
        await SharedCameraStream.open(hass, "camera.test", receive_timestamps=True)
    assert stream.update_source.call_count == 2
    assert outputs == {"hls": other}
