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
from collections.abc import Generator
import logging
import threading
from typing import Any
from unittest.mock import Mock, patch

from aiohttp import web
import pytest

from homeassistant.components.stream.core import StreamOutput
from homeassistant.components.stream.worker import StreamState

from .common import generate_h264_video, stream_teardown

_LOGGER = logging.getLogger(__name__)

TEST_TIMEOUT = 7.0  # Lower than 9s home assistant timeout


class WorkerSync:
    """Test fixture that intercepts stream worker calls to StreamOutput."""

    def __init__(self) -> None:
        """Initialize WorkerSync."""
        self._event = None
        self._original = StreamState.discontinuity

    def pause(self):
        """Pause the worker before it finalizes the stream."""
        self._event = threading.Event()

    def resume(self):
        """Allow the worker thread to finalize the stream."""
        _LOGGER.debug("waking blocked worker")
        self._event.set()

    def blocking_discontinuity(self, stream_state: StreamState):
        """Intercept call to pause stream worker."""
        # Worker is ending the stream, which clears all output buffers.
        # Block the worker thread until the test has a chance to verify
        # the segments under test.
        _LOGGER.debug("blocking worker")
        if self._event:
            self._event.wait()

        # Forward to actual implementation
        self._original(stream_state)


@pytest.fixture
def stream_worker_sync() -> Generator[WorkerSync]:
    """Patch StreamOutput to allow test to synchronize worker stream end."""
    sync = WorkerSync()
    with patch(
        "homeassistant.components.stream.worker.StreamState.discontinuity",
        side_effect=sync.blocking_discontinuity,
        autospec=True,
    ):
        yield sync


class HLSSync:
    """Test fixture that intercepts stream worker calls to StreamOutput."""

    def __init__(self) -> None:
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

        def on_resp():
            self._num_finished += 1
            self.check_requests_ready()

        class SyncResponse(web.Response):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                on_resp()

        self.response = SyncResponse

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


@pytest.fixture
def hls_sync():
    """Patch HLSOutput to allow test to synchronize playlist requests and responses."""
    sync = HLSSync()
    with (
        patch(
            "homeassistant.components.stream.core.StreamOutput.recv",
            side_effect=sync.recv,
            autospec=True,
        ),
        patch(
            "homeassistant.components.stream.core.StreamOutput.part_recv",
            side_effect=sync.part_recv,
            autospec=True,
        ),
        patch(
            "homeassistant.components.stream.hls.web.HTTPBadRequest",
            side_effect=sync.bad_request,
        ),
        patch(
            "homeassistant.components.stream.hls.web.HTTPNotFound",
            side_effect=sync.not_found,
        ),
        patch(
            "homeassistant.components.stream.hls.web.Response",
            new=sync.response,
        ),
    ):
        yield sync


@pytest.fixture(autouse=True)
def should_retry() -> Generator[Mock]:
    """Fixture to disable stream worker retries in tests by default."""
    with patch(
        "homeassistant.components.stream._should_retry", return_value=False
    ) as mock_should_retry:
        yield mock_should_retry


@pytest.fixture(scope="package")
def h264_video():
    """Generate a video, shared across tests."""
    return generate_h264_video()


@pytest.fixture(scope="package", autouse=True)
def fixture_teardown():
    """Destroy package level test state."""
    yield
    stream_teardown()
