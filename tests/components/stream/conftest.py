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
from http import HTTPStatus
import logging
import threading
from unittest.mock import patch

from aiohttp import web
import async_timeout
import pytest

from homeassistant.components.stream.core import Segment, StreamOutput
from homeassistant.components.stream.worker import SegmentBuffer

TEST_TIMEOUT = 7.0  # Lower than 9s home assistant timeout


class WorkerSync:
    """Test fixture that intercepts stream worker calls to StreamOutput."""

    def __init__(self):
        """Initialize WorkerSync."""
        self._event = None
        self._original = SegmentBuffer.discontinuity

    def pause(self):
        """Pause the worker before it finalizes the stream."""
        self._event = threading.Event()

    def resume(self):
        """Allow the worker thread to finalize the stream."""
        logging.debug("waking blocked worker")
        self._event.set()

    def blocking_discontinuity(self, stream: SegmentBuffer):
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
        "homeassistant.components.stream.worker.SegmentBuffer.discontinuity",
        side_effect=sync.blocking_discontinuity,
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
        async with async_timeout.timeout(TEST_TIMEOUT):
            await self._save_event.wait()
        return self._segments

    async def join(self):
        """Verify save worker was invoked and block on shutdown."""
        async with async_timeout.timeout(TEST_TIMEOUT):
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


class HLSSync:
    """Test fixture that intercepts stream worker calls to StreamOutput."""

    def __init__(self):
        """Initialize HLSSync."""
        self._request_event = asyncio.Event()
        self._original_recv = StreamOutput.recv
        self._original_part_recv = StreamOutput.part_recv
        self._original_bad_request = web.HTTPBadRequest
        self._original_not_found = web.HTTPNotFound
        self._original_response = web.Response
        self._num_requests = 0
        self._num_recvs = 0
        self._num_finished = 0

    def reset_request_pool(self, num_requests: int, reset_finished=True):
        """Use to reset the request counter between segments."""
        self._num_recvs = 0
        if reset_finished:
            self._num_finished = 0
        self._num_requests = num_requests

    async def wait_for_handler(self):
        """Set up HLSSync to block calls to put until requests are set up."""
        if not self.check_requests_ready():
            await self._request_event.wait()
        self.reset_request_pool(num_requests=self._num_requests, reset_finished=False)

    def check_requests_ready(self):
        """Unblock the pending put call if the requests are all finished or blocking."""
        if self._num_recvs + self._num_finished == self._num_requests:
            self._request_event.set()
            self._request_event.clear()
            return True
        return False

    def bad_request(self):
        """Intercept the HTTPBadRequest call so we know when the web handler is finished."""
        self._num_finished += 1
        self.check_requests_ready()
        return self._original_bad_request()

    def not_found(self):
        """Intercept the HTTPNotFound call so we know when the web handler is finished."""
        self._num_finished += 1
        self.check_requests_ready()
        return self._original_not_found()

    def response(self, body, headers, status=HTTPStatus.OK):
        """Intercept the Response call so we know when the web handler is finished."""
        self._num_finished += 1
        self.check_requests_ready()
        return self._original_response(body=body, headers=headers, status=status)

    async def recv(self, output: StreamOutput, **kw):
        """Intercept the recv call so we know when the response is blocking on recv."""
        self._num_recvs += 1
        self.check_requests_ready()
        return await self._original_recv(output)

    async def part_recv(self, output: StreamOutput, **kw):
        """Intercept the recv call so we know when the response is blocking on recv."""
        self._num_recvs += 1
        self.check_requests_ready()
        return await self._original_part_recv(output)


@pytest.fixture()
def hls_sync():
    """Patch HLSOutput to allow test to synchronize playlist requests and responses."""
    sync = HLSSync()
    with patch(
        "homeassistant.components.stream.core.StreamOutput.recv",
        side_effect=sync.recv,
        autospec=True,
    ), patch(
        "homeassistant.components.stream.core.StreamOutput.part_recv",
        side_effect=sync.part_recv,
        autospec=True,
    ), patch(
        "homeassistant.components.stream.hls.web.HTTPBadRequest",
        side_effect=sync.bad_request,
    ), patch(
        "homeassistant.components.stream.hls.web.HTTPNotFound",
        side_effect=sync.not_found,
    ), patch(
        "homeassistant.components.stream.hls.web.Response",
        side_effect=sync.response,
    ):
        yield sync
