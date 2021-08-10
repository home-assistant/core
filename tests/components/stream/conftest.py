"""Test fixtures for the stream component.

The tests encode stream (as an h264 video), then load the stream and verify
that it is decoded properly. The background worker thread responsible for
decoding will decode the stream as fast as possible, and when completed
clears all output buffers. This can be a problem for the test that wishes
to retrieve and verify decoded segments. If the worker finishes first, there is
nothing for the test to verify. The solution is the WorkerSync class that
allows the tests to pause the worker thread before finalizing the stream
so that it can inspect the output.
"""
from __future__ import annotations

import asyncio
from collections import deque
import logging
import threading
from unittest.mock import patch

import async_timeout
import pytest

from homeassistant.components.stream import Stream
from homeassistant.components.stream.core import Segment

TEST_TIMEOUT = 7.0  # Lower than 9s home assistant timeout


class WorkerSync:
    """Test fixture that intercepts stream worker calls to StreamOutput."""

    def __init__(self):
        """Initialize WorkerSync."""
        self._event = None
        self._original = Stream._worker_finished

    def pause(self):
        """Pause the worker before it finalizes the stream."""
        self._event = threading.Event()

    def resume(self):
        """Allow the worker thread to finalize the stream."""
        logging.debug("waking blocked worker")
        self._event.set()

    def blocking_finish(self, stream: Stream):
        """Intercept call to pause stream worker."""
        # Worker is ending the stream, which clears all output buffers.
        # Block the worker thread until the test has a chance to verify
        # the segments under test.
        logging.debug("blocking worker")
        if self._event:
            self._event.wait()

        # Forward to actual implementation
        self._original(stream)


@pytest.fixture()
def stream_worker_sync(hass):
    """Patch StreamOutput to allow test to synchronize worker stream end."""
    sync = WorkerSync()
    with patch(
        "homeassistant.components.stream.Stream._worker_finished",
        side_effect=sync.blocking_finish,
        autospec=True,
    ):
        yield sync


class SaveRecordWorkerSync:
    """
    Test fixture to manage RecordOutput thread for recorder_save_worker.

    This is used to assert that the worker is started and stopped cleanly
    to avoid thread leaks in tests.
    """

    def __init__(self):
        """Initialize SaveRecordWorkerSync."""
        self._save_event = None
        self._segments = None
        self._save_thread = None
        self.reset()

    def recorder_save_worker(self, file_out: str, segments: deque[Segment]):
        """Mock method for patch."""
        logging.debug("recorder_save_worker thread started")
        assert self._save_thread is None
        self._segments = segments
        self._save_thread = threading.current_thread()
        self._save_event.set()

    async def get_segments(self):
        """Return the recorded video segments."""
        with async_timeout.timeout(TEST_TIMEOUT):
            await self._save_event.wait()
        return self._segments

    async def join(self):
        """Verify save worker was invoked and block on shutdown."""
        with async_timeout.timeout(TEST_TIMEOUT):
            await self._save_event.wait()
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
