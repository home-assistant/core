"""The tests for hls streams."""
from datetime import timedelta
import logging
import os
import threading
from unittest.mock import patch

import av
import pytest

from homeassistant.components.stream.core import Segment
from homeassistant.components.stream.recorder import recorder_save_worker
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.stream.common import generate_h264_video, preload_stream

TEST_TIMEOUT = 10


class SaveRecordWorkerSync:
    """
    Test fixture to manage RecordOutput thread for recorder_save_worker.

    This is used to assert that the worker is started and stopped cleanly
    to avoid thread leaks in tests.
    """

    def __init__(self):
        """Initialize SaveRecordWorkerSync."""
        self.reset()

    def recorder_save_worker(self, *args, **kwargs):
        """Mock method for patch."""
        logging.debug("recorder_save_worker thread started")
        assert self._save_thread is None
        self._save_thread = threading.current_thread()
        self._save_event.set()

    def join(self):
        """Verify save worker was invoked and block on shutdown."""
        assert self._save_event.wait(timeout=TEST_TIMEOUT)
        self._save_thread.join()

    def reset(self):
        """Reset callback state for reuse in tests."""
        self._save_thread = None
        self._save_event = threading.Event()


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
    stream = preload_stream(hass, source)
    recorder = stream.add_provider("recorder")
    stream.start()

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


async def test_recorder_timeout(hass, hass_client, stream_worker_sync):
    """
    Test recorder timeout.

    Mocks out the cleanup to assert that it is invoked after a timeout.
    This test does not start the recorder save thread.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    stream_worker_sync.pause()

    with patch("homeassistant.components.stream.IdleTimer.fire") as mock_timeout:
        # Setup demo track
        source = generate_h264_video()
        stream = preload_stream(hass, source)
        recorder = stream.add_provider("recorder", timeout=30)
        stream.start()

        await recorder.recv()

        # Wait a minute
        future = dt_util.utcnow() + timedelta(minutes=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert mock_timeout.called

        stream_worker_sync.resume()
        stream.stop()
        await hass.async_block_till_done()
        await hass.async_block_till_done()


async def test_recorder_save(tmpdir):
    """Test recorder save."""
    # Setup
    source = generate_h264_video()
    filename = f"{tmpdir}/test.mp4"

    # Run
    recorder_save_worker(filename, [Segment(1, source, 4)], "mp4")

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
        stream = preload_stream(hass, source)
        recorder = stream.add_provider("recorder")
        stream.start()

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
