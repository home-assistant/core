"""The tests for hls streams."""
import asyncio
from datetime import timedelta
import logging
import os
import threading
from typing import Deque
from unittest.mock import patch

import async_timeout
import av
import pytest

from homeassistant.components.stream import create_stream
from homeassistant.components.stream.core import Segment
from homeassistant.components.stream.recorder import recorder_save_worker
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.stream.common import generate_h264_video

TEST_TIMEOUT = 10
RECORD_DURATION = 30


class SaveRecordWorkerSync:
    """
    Test fixture to manage RecordOutput thread for recorder_save_worker.

    This is used to assert that the worker is started and stopped cleanly
    to avoid thread leaks in tests.
    """

    def __init__(self):
        """Initialize SaveRecordWorkerSync."""
        self.reset()
        self._segments = None

    def recorder_save_worker(self, file_out: str, segments: Deque[Segment]):
        """Mock method for patch."""
        logging.debug("recorder_save_worker thread started")
        self._segments = segments
        assert self._save_thread is None
        self._save_thread = threading.current_thread()
        self._save_event.set()

    async def get_segments(self):
        """Return the recorded video segments."""
        with async_timeout.timeout(TEST_TIMEOUT):
            await self._save_event.wait()
        return self._segments

    def join(self):
        """Verify save worker was invoked and block on shutdown."""
        self._save_thread.join(timeout=TEST_TIMEOUT)
        assert not self._save_thread.is_alive()

    def reset(self):
        """Reset callback state for reuse in tests."""
        self._save_thread = None
        self._save_event = asyncio.Event()


@pytest.fixture()
def record_worker_sync(hass):
    """Patch recorder_save_worker for clean thread shutdown for test."""
    sync = SaveRecordWorkerSync()
    with patch(
        "homeassistant.components.stream.recorder.recorder_save_worker",
        side_effect=sync.recorder_save_worker,
        autospec=True,
    ):
        yield sync


async def test_record_stream(hass, hass_client, stream_worker_sync, record_worker_sync):
    """
    Test record stream.

    Tests full integration with the stream component, and captures the
    stream worker and save worker to allow for clean shutdown of background
    threads.  The actual save logic is tested in test_recorder_save below.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    stream_worker_sync.pause()

    # Setup demo track
    source = generate_h264_video()
    stream = create_stream(hass, source)
    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await stream.async_record("/example/path")

    recorder = stream.add_provider("recorder")
    while True:
        segment = await recorder.recv()
        if not segment:
            break
        segments = segment.sequence
        if segments > 1:
            stream_worker_sync.resume()

    stream.stop()
    assert segments > 1

    # Verify that the save worker was invoked, then block until its
    # thread completes and is shutdown completely to avoid thread leaks.
    record_worker_sync.join()


async def test_record_lookback(
    hass, hass_client, stream_worker_sync, record_worker_sync
):
    """Exercise record with loopback."""
    await async_setup_component(hass, "stream", {"stream": {}})

    source = generate_h264_video()
    stream = create_stream(hass, source)

    # Start an HLS feed to enable lookback
    stream.add_provider("hls")
    stream.start()

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await stream.async_record("/example/path", lookback=4)

    # This test does not need recorder cleanup since it is not fully exercised

    stream.stop()


async def test_recorder_duration(hass, hass_client, stream_worker_sync):
    """
    Test recorder invokes the save function after the duration expires.

    Mocks out the cleanup to assert that it is invoked after a timeout.
    This test does not start the recorder save thread.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    # Prevent the worker thread from exiting before the alarm fires
    stream_worker_sync.pause()

    with patch("homeassistant.components.stream.IdleTimer.fire") as mock_timeout:
        # Setup demo track
        source = generate_h264_video()

        stream = create_stream(hass, source)
        with patch.object(hass.config, "is_allowed_path", return_value=True):
            await stream.async_record("/example/path", duration=RECORD_DURATION)
        recorder = stream.add_provider("recorder")

        # The recorder timer starts when the first packet is received
        await recorder.recv()

        assert not mock_timeout.called

        future = dt_util.utcnow() + timedelta(seconds=RECORD_DURATION + 1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert mock_timeout.called

        stream_worker_sync.resume()
        stream.stop()
        await hass.async_block_till_done()
        await hass.async_block_till_done()


async def test_recorder_duration_keepalive(hass, hass_client, record_worker_sync):
    """Test recorder duration firing on a keepalive stream."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Setup demo track
    source = generate_h264_video()

    stream = create_stream(hass, source)
    stream.keepalive = True
    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await stream.async_record("/example/path", duration=RECORD_DURATION)

    # The recorder timer starts when the first packet is received
    recorder = stream.add_provider("recorder")
    await recorder.recv()

    future = dt_util.utcnow() + timedelta(seconds=RECORD_DURATION + 1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    segments = await record_worker_sync.get_segments()
    assert len(segments) >= 1

    record_worker_sync.join()
    stream.stop()
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def test_record_path_not_allowed(hass, hass_client):
    """Test where the output path is not allowed by home assistant configuration."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Setup demo track
    source = generate_h264_video()
    stream = create_stream(hass, source)
    with patch.object(
        hass.config, "is_allowed_path", return_value=False
    ), pytest.raises(HomeAssistantError):
        await stream.async_record("/example/path")


async def test_recorder_save(tmpdir):
    """Test recorder save."""
    # Setup
    source = generate_h264_video()
    filename = f"{tmpdir}/test.mp4"

    # Run
    recorder_save_worker(filename, [Segment(1, source, 4)])

    # Assert
    assert os.path.exists(filename)


async def test_recorder_discontinuity(tmpdir):
    """Test recorder save across a discontinuity."""
    # Setup
    source = generate_h264_video()
    filename = f"{tmpdir}/test.mp4"

    # Run
    recorder_save_worker(filename, [Segment(1, source, 4, 0), Segment(2, source, 4, 1)])

    # Assert
    assert os.path.exists(filename)


async def test_record_stream_audio(
    hass, hass_client, stream_worker_sync, record_worker_sync
):
    """
    Test treatment of different audio inputs.

    Record stream output should have an audio channel when input has
    a valid codec and audio packets and no audio channel otherwise.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    for a_codec, expected_audio_streams in (
        ("aac", 1),  # aac is a valid mp4 codec
        ("pcm_mulaw", 0),  # G.711 is not a valid mp4 codec
        ("empty", 0),  # audio stream with no packets
        (None, 0),  # no audio stream
    ):
        record_worker_sync.reset()
        stream_worker_sync.pause()

        # Setup demo track
        source = generate_h264_video(
            container_format="mov", audio_codec=a_codec
        )  # mov can store PCM
        stream = create_stream(hass, source)
        with patch.object(hass.config, "is_allowed_path", return_value=True):
            await stream.async_record("/example/path")
        recorder = stream.add_provider("recorder")

        while True:
            segment = await recorder.recv()
            if not segment:
                break
            last_segment = segment
            stream_worker_sync.resume()

        result = av.open(last_segment.segment, "r", format="mp4")

        assert len(result.streams.audio) == expected_audio_streams
        result.close()
        stream.stop()
        await hass.async_block_till_done()

        # Verify that the save worker was invoked, then block until its
        # thread completes and is shutdown completely to avoid thread leaks.
        record_worker_sync.join()
