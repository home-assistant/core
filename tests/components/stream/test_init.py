"""Test stream init."""

import logging
from unittest.mock import MagicMock, patch

import av
import pytest

from homeassistant.components.stream import (
    CONF_PREFER_TCP,
    SOURCE_TIMEOUT,
    StreamClientError,
    StreamOpenClientError,
    __name__ as stream_name,
    _async_try_open_stream,
    async_check_stream_client_error,
)
from homeassistant.const import EVENT_LOGGING_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_log_levels(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that the worker logs the url without username and password."""

    await async_setup_component(hass, "stream", {"stream": {}})

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

    container_mock = MagicMock()
    source = "rtsp://foobar"

    with patch("av.open", return_value=container_mock) as open_mock:
        await async_check_stream_client_error(hass, source)

    options = {
        "rtsp_flags": CONF_PREFER_TCP,
        "timeout": str(SOURCE_TIMEOUT),
    }
    open_mock.assert_called_once_with(source, options=options, timeout=5)
    container_mock.close.assert_called_once()

    container_mock.reset_mock()
    with patch("av.open", return_value=container_mock) as open_mock:
        await async_check_stream_client_error(hass, source, {"foo": "bar"})

    options = {
        "rtsp_flags": CONF_PREFER_TCP,
        "timeout": str(SOURCE_TIMEOUT),
        "foo": "bar",
    }
    open_mock.assert_called_once_with(source, options=options, timeout=5)
    container_mock.close.assert_called_once()


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
    oc_error: StreamOpenClientError | None = None

    with patch("av.open", side_effect=error):
        try:
            await _async_try_open_stream(hass, "rtsp://foobar")
        except StreamOpenClientError as ex:
            oc_error = ex

    assert oc_error
    assert oc_error.stream_client_error is enum_result
