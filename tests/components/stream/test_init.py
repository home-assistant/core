"""Test stream init."""

import asyncio
import io
import logging
import threading
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import av
import pytest

from homeassistant.components.stream import (
    SOURCE_TIMEOUT,
    StreamClientError,
    StreamOpenClientError,
    __name__ as stream_name,
    _WorkerControl,
    async_check_stream_client_error,
    create_stream,
)
from homeassistant.components.stream.const import ATTR_PREFER_TCP, DOMAIN, HLS_PROVIDER
from homeassistant.const import CONF_VERIFY_SSL, EVENT_LOGGING_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import dynamic_stream_settings

TIMEOUT = 15
STREAM_SOURCE = "rtsp://foobar"


async def test_stream_not_setup(hass: HomeAssistant, h264_video) -> None:
    """Test hls stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """
    with pytest.raises(HomeAssistantError, match="Stream integration is not set up"):
        create_stream(hass, "rtsp://foobar", {}, dynamic_stream_settings())

    with pytest.raises(HomeAssistantError, match="Stream integration is not set up"):
        await async_check_stream_client_error(hass, "rtsp://foobar")


async def test_log_levels(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that the worker logs the url without username and password."""

    await async_setup_component(hass, DOMAIN, {"stream": {}})

    # These namespaces should only pass log messages when the stream logger
    # is at logging.DEBUG or below
    namespaces_to_toggle = (
        "mp4",
        "h264",
        "hevc",
        "rtsp",
        "tcp",
        "tls",
        "mpegts",
        "NULL",
    )

    logging.getLogger(stream_name).setLevel(logging.INFO)
    hass.bus.async_fire(EVENT_LOGGING_CHANGED)
    await hass.async_block_till_done()

    # Since logging is at INFO, these should not pass
    for namespace in namespaces_to_toggle:
        av.logging.log(av.logging.ERROR, namespace, "SHOULD NOT PASS")

    logging.getLogger(stream_name).setLevel(logging.DEBUG)
    hass.bus.async_fire(EVENT_LOGGING_CHANGED)
    await hass.async_block_till_done()

    # Since logging is now at DEBUG, these should now pass
    for namespace in namespaces_to_toggle:
        av.logging.log(av.logging.ERROR, namespace, "SHOULD PASS")

    # Even though logging is at DEBUG, these should not pass
    av.logging.log(av.logging.WARNING, "mp4", "SHOULD NOT PASS")
    av.logging.log(av.logging.WARNING, "swscaler", "SHOULD NOT PASS")

    assert "SHOULD PASS" in caplog.text
    assert "SHOULD NOT PASS" not in caplog.text


async def test_check_open_stream_params(hass: HomeAssistant) -> None:
    """Test check open stream params."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})

    container_mock = MagicMock()
    source = "rtsp://foobar"

    with patch("av.open", return_value=container_mock) as open_mock:
        await async_check_stream_client_error(hass, source)

    options = {
        "rtsp_flags": ATTR_PREFER_TCP,
        "stimeout": "5000000",
        "tls_verify": "0",
    }
    open_mock.assert_called_once_with(source, options=options, timeout=SOURCE_TIMEOUT)
    container_mock.close.assert_called_once()

    container_mock.reset_mock()
    with (
        patch("av.open", return_value=container_mock) as open_mock,
        pytest.raises(HomeAssistantError, match="Invalid stream options"),
    ):
        await async_check_stream_client_error(hass, source, {"foo": "bar"})


@pytest.mark.parametrize(
    ("error", "enum_result"),
    [
        pytest.param(
            av.HTTPBadRequestError(400, ""),
            StreamClientError.BadRequest,
            id="BadRequest",
        ),
        pytest.param(
            av.HTTPUnauthorizedError(401, ""),
            StreamClientError.Unauthorized,
            id="Unauthorized",
        ),
        pytest.param(
            av.HTTPForbiddenError(403, ""), StreamClientError.Forbidden, id="Forbidden"
        ),
        pytest.param(
            av.HTTPNotFoundError(404, ""), StreamClientError.NotFound, id="NotFound"
        ),
        pytest.param(
            av.HTTPOtherClientError(408, ""), StreamClientError.Other, id="Other"
        ),
    ],
)
async def test_try_open_stream_error(
    hass: HomeAssistant, error: av.HTTPClientError, enum_result: StreamClientError
) -> None:
    """Test trying to open a stream."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})

    with (
        patch("av.open", side_effect=error),
        pytest.raises(StreamOpenClientError) as ex,
    ):
        await async_check_stream_client_error(hass, "rtsp://foobar")
    assert ex.value.error_code is enum_result


@pytest.mark.parametrize(
    ("options", "expected_pyav_options"),
    [
        (
            {},
            {"rtsp_flags": "prefer_tcp", "stimeout": "5000000", "tls_verify": "0"},
        ),
        (
            {"rtsp_transport": "udp"},
            {
                "rtsp_flags": "prefer_tcp",
                "rtsp_transport": "udp",
                "stimeout": "5000000",
                "tls_verify": "0",
            },
        ),
        (
            {"use_wallclock_as_timestamps": True},
            {
                "rtsp_flags": "prefer_tcp",
                "stimeout": "5000000",
                "tls_verify": "0",
                "use_wallclock_as_timestamps": "1",
            },
        ),
    ],
)
async def test_convert_stream_options(
    hass: HomeAssistant,
    options: dict[str, Any],
    expected_pyav_options: dict[str, Any],
) -> None:
    """Test stream options."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})

    container_mock = MagicMock()
    source = "rtsp://foobar"

    with patch("av.open", return_value=container_mock) as open_mock:
        await async_check_stream_client_error(hass, source, options)

    open_mock.assert_called_once_with(
        source, options=expected_pyav_options, timeout=SOURCE_TIMEOUT
    )
    container_mock.close.assert_called_once()


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("rtsps://foobar", id="rtsps"),
        pytest.param("https://foobar", id="https"),
        # an http source can redirect to https
        pytest.param("http://foobar", id="http"),
    ],
)
async def test_tls_verify_disabled(hass: HomeAssistant, source: str) -> None:
    """Test TLS certificate verification is disabled for non-RTSP sources."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})

    with patch("av.open") as open_mock:
        await async_check_stream_client_error(hass, source)

    open_mock.assert_called_once_with(
        source, options={"tls_verify": "0"}, timeout=SOURCE_TIMEOUT
    )


@pytest.mark.parametrize(
    ("verify_ssl", "tls_verify"),
    [
        pytest.param(True, "1", id="enabled"),
        pytest.param(False, "0", id="disabled"),
    ],
)
async def test_verify_ssl_option(
    hass: HomeAssistant, verify_ssl: bool, tls_verify: str
) -> None:
    """Test the verify_ssl stream option controls TLS certificate verification."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    source = "rtsps://foobar"

    with patch("av.open") as open_mock:
        await async_check_stream_client_error(
            hass, source, {CONF_VERIFY_SSL: verify_ssl}
        )

    open_mock.assert_called_once_with(
        source, options={"tls_verify": tls_verify}, timeout=SOURCE_TIMEOUT
    )


async def test_stop_during_pending_source_update(
    hass: HomeAssistant, h264_video: io.BytesIO
) -> None:
    """Test that stop() is not lost when an update_source() restart is pending."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    worker_open = threading.Event()
    worker_wake = threading.Event()
    opened_sources: list[str] = []
    real_open = av.open

    def blocking_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            worker_open.set()
            worker_wake.wait()
            return real_open(io.BytesIO(h264_video.getvalue()))
        return real_open(stream_source, *args, **kwargs)

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)

    with patch("av.open", new=blocking_open):
        try:
            await stream.start()
            assert await hass.async_add_executor_job(worker_open.wait, TIMEOUT)

            stream.update_source(f"{STREAM_SOURCE}-updated")
            stop_task = hass.async_create_task(stream.stop())
            await asyncio.sleep(0)
            worker_wake.set()
            await stop_task

            assert opened_sources == [STREAM_SOURCE]
        finally:
            worker_wake.set()
            await stream.stop()


async def test_update_source_while_stopping(
    hass: HomeAssistant, h264_video: io.BytesIO
) -> None:
    """Test that update_source() does not undo a stop() in progress."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    worker_open = threading.Event()
    worker_wake = threading.Event()
    opened_sources: list[str] = []
    real_open = av.open

    def blocking_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            worker_open.set()
            worker_wake.wait()
            return real_open(io.BytesIO(h264_video.getvalue()))
        return real_open(stream_source, *args, **kwargs)

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)

    with patch("av.open", new=blocking_open):
        try:
            await stream.start()
            assert await hass.async_add_executor_job(worker_open.wait, TIMEOUT)

            stop_task = hass.async_create_task(stream.stop())
            await asyncio.sleep(0)
            stream.update_source(f"{STREAM_SOURCE}-updated")
            worker_wake.set()
            await stop_task

            assert opened_sources == [STREAM_SOURCE]
        finally:
            worker_wake.set()
            await stream.stop()


async def test_update_source_during_retry_backoff(
    hass: HomeAssistant, h264_video: io.BytesIO, should_retry: Mock
) -> None:
    """Test that update_source() wakes the worker during retry backoff."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    should_retry.return_value = True
    worker_open = threading.Event()
    worker_wake = threading.Event()
    in_backoff = asyncio.Event()
    opened_sources: list[str] = []
    real_open = av.open

    def blocking_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            if len(opened_sources) == 1:
                raise av.FFmpegError(1, "Simulated open failure")
            worker_open.set()
            worker_wake.wait()
            return real_open(io.BytesIO(h264_video.getvalue()))
        return real_open(stream_source, *args, **kwargs)

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)
    stream.set_update_callback(lambda: None if stream.available else in_backoff.set())

    with (
        patch("av.open", new=blocking_open),
        patch("homeassistant.components.stream.STREAM_RESTART_INCREMENT", 3600),
    ):
        try:
            await stream.start()
            await asyncio.wait_for(in_backoff.wait(), TIMEOUT)
            assert not stream.available

            updated_source = f"{STREAM_SOURCE}-updated"
            stream.update_source(updated_source)
            assert await hass.async_add_executor_job(worker_open.wait, TIMEOUT)
            assert opened_sources == [STREAM_SOURCE, updated_source]
        finally:
            worker_wake.set()
            await stream.stop()


async def test_output_added_while_stopping_is_kept(
    hass: HomeAssistant, h264_video: io.BytesIO, should_retry: Mock
) -> None:
    """Test that an output added while the stream stops survives the restart."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    should_retry.return_value = True
    worker_open = threading.Event()
    worker_wake = threading.Event()
    opened_sources: list[str] = []
    real_open = av.open

    def blocking_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            worker_open.set()
            worker_wake.wait()
            return real_open(io.BytesIO(h264_video.getvalue()))
        return real_open(stream_source, *args, **kwargs)

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    output = stream.add_provider(HLS_PROVIDER)

    with patch("av.open", new=blocking_open):
        try:
            await stream.start()
            assert await hass.async_add_executor_job(worker_open.wait, TIMEOUT)

            # Last viewer leaves: stream stops while its worker is still busy
            stop_task = hass.async_create_task(stream.remove_provider(output))
            await asyncio.sleep(0)

            # New viewer arrives before the old worker exits
            worker_open.clear()
            new_output = stream.add_provider(HLS_PROVIDER)
            start_task = hass.async_create_task(stream.start())
            worker_wake.set()
            await stop_task
            await start_task
            await hass.async_block_till_done()

            assert stream.outputs() == {HLS_PROVIDER: new_output}
            assert stream.endpoint_url(HLS_PROVIDER).startswith("/api/hls/")
            assert await hass.async_add_executor_job(worker_open.wait, TIMEOUT)
            assert opened_sources == [STREAM_SOURCE, STREAM_SOURCE]
        finally:
            worker_wake.set()
            await stream.stop()


async def test_start_after_cancelled_stop_waits_for_worker(
    hass: HomeAssistant, h264_video: io.BytesIO, should_retry: Mock
) -> None:
    """Test that start() waits for a stopping worker after a cancelled stop()."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    should_retry.return_value = True
    worker_open = threading.Event()
    first_wake = threading.Event()
    second_wake = threading.Event()
    opened_sources: list[str] = []
    real_open = av.open

    def blocking_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            worker_open.set()
            if len(opened_sources) == 1:
                first_wake.wait()
            else:
                second_wake.wait()
            return real_open(io.BytesIO(h264_video.getvalue()))
        return real_open(stream_source, *args, **kwargs)

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)

    with patch("av.open", new=blocking_open):
        try:
            await stream.start()
            assert await hass.async_add_executor_job(worker_open.wait, TIMEOUT)

            stop_task = hass.async_create_task(stream.stop())
            await asyncio.sleep(0)
            stop_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await stop_task

            # start() must not launch a second worker until the first exits
            worker_open.clear()
            stream.add_provider(HLS_PROVIDER)
            start_task = hass.async_create_task(stream.start())
            await asyncio.sleep(0)
            assert not start_task.done()
            assert opened_sources == [STREAM_SOURCE]

            first_wake.set()
            await start_task
            assert await hass.async_add_executor_job(worker_open.wait, TIMEOUT)
            assert opened_sources == [STREAM_SOURCE, STREAM_SOURCE]
        finally:
            first_wake.set()
            second_wake.set()
            await stream.stop()


async def test_stop_during_retry_backoff(
    hass: HomeAssistant, should_retry: Mock
) -> None:
    """Test that stop() during retry backoff ends the worker without a retry."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    should_retry.return_value = True
    in_backoff = asyncio.Event()
    opened_sources: list[str] = []
    real_open = av.open

    def failing_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            raise av.FFmpegError(1, "Simulated open failure")
        return real_open(stream_source, *args, **kwargs)

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)
    stream.set_update_callback(lambda: None if stream.available else in_backoff.set())

    with (
        patch("av.open", new=failing_open),
        patch("homeassistant.components.stream.STREAM_RESTART_INCREMENT", 3600),
    ):
        await stream.start()
        await asyncio.wait_for(in_backoff.wait(), TIMEOUT)
        thread = stream._thread
        await asyncio.wait_for(stream.stop(), TIMEOUT)

    assert not thread.is_alive()
    assert opened_sources == [STREAM_SOURCE]


async def test_stop_during_retry_backoff_with_pending_source_update(
    hass: HomeAssistant, should_retry: Mock
) -> None:
    """Test that stop() wins over an update_source() that woke the retry backoff."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    should_retry.return_value = True
    in_backoff = asyncio.Event()
    restart_seen = threading.Event()
    restart_release = threading.Event()
    opened_sources: list[str] = []
    real_open = av.open

    def failing_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            raise av.FFmpegError(1, "Simulated open failure")
        return real_open(stream_source, *args, **kwargs)

    class HeldWorkerControl(_WorkerControl):
        """Holds the worker just before it takes a pending restart."""

        def begin_attempt(self) -> tuple[str | None, bool]:
            if self._restart:
                restart_seen.set()
                restart_release.wait(TIMEOUT)
            return super().begin_attempt()

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)
    stream.set_update_callback(lambda: None if stream.available else in_backoff.set())

    with (
        patch("av.open", new=failing_open),
        patch("homeassistant.components.stream.STREAM_RESTART_INCREMENT", 3600),
        patch("homeassistant.components.stream._WorkerControl", HeldWorkerControl),
    ):
        try:
            await stream.start()
            await asyncio.wait_for(in_backoff.wait(), TIMEOUT)
            thread = stream._thread
            control = stream._worker_control

            stream.update_source(f"{STREAM_SOURCE}-updated")
            assert await hass.async_add_executor_job(restart_seen.wait, TIMEOUT)
            stop_task = hass.async_create_task(stream.stop())
            await asyncio.sleep(0)
            assert control.is_stopped
            restart_release.set()
            await asyncio.wait_for(stop_task, TIMEOUT)
        finally:
            restart_release.set()
            await stream.stop()

    assert not thread.is_alive()
    assert opened_sources == [STREAM_SOURCE]


async def test_update_source_before_retry_attempt_opens_once(
    hass: HomeAssistant, h264_video: io.BytesIO, should_retry: Mock
) -> None:
    """Test update_source() right as a retry starts does not open the new source twice."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})
    should_retry.return_value = True
    updated_source = f"{STREAM_SOURCE}-updated"
    opened_sources: list[str] = []
    real_open = av.open

    def fake_open(stream_source: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(stream_source, str):
            opened_sources.append(stream_source)
            if len(opened_sources) == 1:
                raise av.FFmpegError(1, "Simulated open failure")
            should_retry.return_value = False
            return real_open(io.BytesIO(h264_video.getvalue()))
        return real_open(stream_source, *args, **kwargs)

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)
    real_set_state = stream._set_state

    def trigger_update_on_retry(available: bool) -> None:
        if (
            available
            and opened_sources == [STREAM_SOURCE]
            and stream.source != updated_source
        ):
            stream.update_source(updated_source)
        real_set_state(available)

    with (
        patch("av.open", new=fake_open),
        patch("homeassistant.components.stream.STREAM_RESTART_INCREMENT", 0.01),
        patch.object(stream, "_set_state", side_effect=trigger_update_on_retry),
    ):
        await stream.start()
        assert stream._thread is not None
        await hass.async_add_executor_job(stream._thread.join, TIMEOUT)
        await stream.stop()

    assert opened_sources == [STREAM_SOURCE, updated_source]
