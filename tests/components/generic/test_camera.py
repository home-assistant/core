"""The tests for generic camera component."""
import asyncio
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import httpx
import pytest
import respx

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    async_get_mjpeg_stream,
    async_get_stream_source,
)
from homeassistant.components.generic.const import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    DOMAIN,
)
from homeassistant.components.stream.const import CONF_RTSP_TRANSPORT
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import Mock, MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def help_setup_mock_config_entry(
    hass: HomeAssistant, options: dict[str, Any], unique_id: Any | None = None
) -> MockConfigEntry:
    """Help setting up a generic camera config entry."""
    entry_options = {
        CONF_STILL_IMAGE_URL: options.get(CONF_STILL_IMAGE_URL),
        CONF_STREAM_SOURCE: options.get(CONF_STREAM_SOURCE),
        CONF_AUTHENTICATION: options.get(CONF_AUTHENTICATION),
        CONF_USERNAME: options.get(CONF_USERNAME),
        CONF_PASSWORD: options.get(CONF_PASSWORD),
        CONF_LIMIT_REFETCH_TO_URL_CHANGE: options.get(
            CONF_LIMIT_REFETCH_TO_URL_CHANGE, False
        ),
        CONF_CONTENT_TYPE: options.get(CONF_CONTENT_TYPE, DEFAULT_CONTENT_TYPE),
        CONF_FRAMERATE: options.get(CONF_FRAMERATE, 2),
        CONF_VERIFY_SSL: options.get(CONF_VERIFY_SSL),
    }
    entry = MockConfigEntry(
        domain="generic",
        title=options[CONF_NAME],
        options=entry_options,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    return entry


@respx.mock
async def test_fetching_url(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fakeimgbytes_png,
    caplog: pytest.CaptureFixture,
) -> None:
    """Test that it fetches the given url."""
    hass.states.async_set("sensor.temp", "http://example.com/0a")
    respx.get("http://example.com/0a").respond(stream=fakeimgbytes_png)
    respx.get("http://example.com/1a").respond(stream=fakeimgbytes_png)

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "{{ states.sensor.temp.state }}",
        "username": "user",
        "password": "pass",
        "authentication": "basic",
        "framerate": 20,
    }
    await help_setup_mock_config_entry(hass, options)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == HTTPStatus.OK
    assert respx.calls.call_count == 1
    body = await resp.read()
    assert body == fakeimgbytes_png

    # sleep .1 seconds to make cached image expire
    await asyncio.sleep(0.1)

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 2

    # If the template renders to an invalid URL we return the last image from cache
    hass.states.async_set("sensor.temp", "invalid url")

    # sleep another .1 seconds to make cached image expire
    await asyncio.sleep(0.1)
    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert resp.status == HTTPStatus.OK
    assert respx.calls.call_count == 2
    assert (
        "Invalid URL 'invalid url': expected a URL, returning last image" in caplog.text
    )

    # Restore a valid URL
    hass.states.async_set("sensor.temp", "http://example.com/1a")
    await asyncio.sleep(0.1)
    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert resp.status == HTTPStatus.OK
    assert respx.calls.call_count == 3


@respx.mock
async def test_image_caching(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    fakeimgbytes_png,
) -> None:
    """Test that the image is cached and not fetched more often than the framerate indicates."""
    respx.get("http://example.com").respond(stream=fakeimgbytes_png)

    framerate = 5
    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "http://example.com",
        "username": "user",
        "password": "pass",
        "authentication": "basic",
        "framerate": framerate,
    }
    await help_setup_mock_config_entry(hass, options)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_png

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_png

    # time is frozen, image should have come from cache
    assert respx.calls.call_count == 1

    # advance time by 150ms
    freezer.tick(timedelta(seconds=0.150))

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_png

    # Only 150ms have passed, image should still have come from cache
    assert respx.calls.call_count == 1

    # advance time by another 150ms
    freezer.tick(timedelta(seconds=0.150))

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_png

    # 300ms have passed, now we should have fetched a new image
    assert respx.calls.call_count == 2

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_png

    # Still only 300ms have passed, should have returned the cached image
    assert respx.calls.call_count == 2


@respx.mock
async def test_fetching_without_verify_ssl(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, fakeimgbytes_png
) -> None:
    """Test that it fetches the given url when ssl verify is off."""
    respx.get("https://example.com").respond(stream=fakeimgbytes_png)

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "https://example.com",
        "username": "user",
        "password": "pass",
        "verify_ssl": "false",
    }
    await help_setup_mock_config_entry(hass, options)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == HTTPStatus.OK


@respx.mock
async def test_fetching_url_with_verify_ssl(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, fakeimgbytes_png
) -> None:
    """Test that it fetches the given url when ssl verify is explicitly on."""
    respx.get("https://example.com").respond(stream=fakeimgbytes_png)

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "https://example.com",
        "username": "user",
        "password": "pass",
        "verify_ssl": True,
    }
    await help_setup_mock_config_entry(hass, options)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == HTTPStatus.OK


@respx.mock
async def test_limit_refetch(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fakeimgbytes_png,
    fakeimgbytes_jpg,
) -> None:
    """Test that it fetches the given url."""
    respx.get("http://example.com/0a").respond(stream=fakeimgbytes_png)
    respx.get("http://example.com/5a").respond(stream=fakeimgbytes_png)
    respx.get("http://example.com/10a").respond(stream=fakeimgbytes_png)
    respx.get("http://example.com/15a").respond(stream=fakeimgbytes_jpg)
    respx.get("http://example.com/20a").respond(status_code=HTTPStatus.NOT_FOUND)

    hass.states.async_set("sensor.temp", "0")

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": 'http://example.com/{{ states.sensor.temp.state + "a" }}',
        "limit_refetch_to_url_change": True,
    }
    await help_setup_mock_config_entry(hass, options)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    hass.states.async_set("sensor.temp", "5")

    with pytest.raises(aiohttp.ServerTimeoutError), patch(
        "asyncio.timeout", side_effect=TimeoutError()
    ):
        resp = await client.get("/api/camera_proxy/camera.config_test")

    assert respx.calls.call_count == 1
    assert resp.status == HTTPStatus.OK

    hass.states.async_set("sensor.temp", "10")

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 2
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_png

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 2
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_png

    hass.states.async_set("sensor.temp", "15")

    # Url change = fetch new image
    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 3
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_jpg

    # Cause a template render error
    hass.states.async_remove("sensor.temp")
    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 3
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == fakeimgbytes_jpg


@respx.mock
async def test_stream_source(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    fakeimgbytes_png,
) -> None:
    """Test that the stream source is rendered."""
    respx.get("http://example.com").respond(stream=fakeimgbytes_png)
    respx.get("http://example.com/0a").respond(stream=fakeimgbytes_png)

    hass.states.async_set("sensor.temp", "0")
    mock_entry = MockConfigEntry(
        title="config_test",
        domain=DOMAIN,
        data={},
        options={
            CONF_STILL_IMAGE_URL: "http://example.com",
            CONF_STREAM_SOURCE: 'http://example.com/{{ states.sensor.temp.state + "a" }}',
            CONF_LIMIT_REFETCH_TO_URL_CHANGE: True,
            CONF_FRAMERATE: 2,
            CONF_CONTENT_TYPE: "image/png",
            CONF_VERIFY_SSL: False,
            CONF_USERNAME: "barney",
            CONF_PASSWORD: "betty",
            CONF_RTSP_TRANSPORT: "http",
        },
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert await async_setup_component(hass, "stream", {})
    await hass.async_block_till_done()

    hass.states.async_set("sensor.temp", "5")
    stream_source = await async_get_stream_source(hass, "camera.config_test")
    assert stream_source == "http://barney:betty@example.com/5a"

    with patch(
        "homeassistant.components.camera.Stream.endpoint_url",
        return_value="http://home.assistant/playlist.m3u8",
    ) as mock_stream_url:
        # Request playlist through WebSocket
        client = await hass_ws_client(hass)

        await client.send_json(
            {"id": 1, "type": "camera/stream", "entity_id": "camera.config_test"}
        )
        msg = await client.receive_json()

        # Assert WebSocket response
        assert mock_stream_url.call_count == 1
        assert msg["id"] == 1
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        assert msg["result"]["url"][-13:] == "playlist.m3u8"


@respx.mock
async def test_stream_source_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    fakeimgbytes_png,
) -> None:
    """Test that the stream source has an error."""
    respx.get("http://example.com").respond(stream=fakeimgbytes_png)

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "http://example.com",
        # Does not exist
        "stream_source": 'http://example.com/{{ states.sensor.temp.state + "a" }}',
        "limit_refetch_to_url_change": True,
    }
    await help_setup_mock_config_entry(hass, options)
    assert await async_setup_component(hass, "stream", {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.camera.Stream.endpoint_url",
        return_value="http://home.assistant/playlist.m3u8",
    ) as mock_stream_url:
        # Request playlist through WebSocket
        client = await hass_ws_client(hass)

        await client.send_json(
            {"id": 1, "type": "camera/stream", "entity_id": "camera.config_test"}
        )
        msg = await client.receive_json()

        # Assert WebSocket response
        assert mock_stream_url.call_count == 0
        assert msg["id"] == 1
        assert msg["type"] == TYPE_RESULT
        assert msg["success"] is False
        assert msg["error"] == {
            "code": "start_stream_failed",
            "message": "camera.config_test does not support play stream service",
        }


@respx.mock
async def test_setup_alternative_options(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, fakeimgbytes_png
) -> None:
    """Test that the stream source is setup with different config options."""
    respx.get("https://example.com").respond(stream=fakeimgbytes_png)

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "https://example.com",
        "authentication": "digest",
        "username": "user",
        "password": "pass",
        "stream_source": "rtsp://example.com:554/rtsp/",
        "rtsp_transport": "udp",
    }
    await help_setup_mock_config_entry(hass, options)
    assert hass.states.get("camera.config_test")


@respx.mock
async def test_no_stream_source(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    fakeimgbytes_png,
) -> None:
    """Test a stream request without stream source option set."""
    respx.get("https://example.com").respond(stream=fakeimgbytes_png)

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "https://example.com",
        "limit_refetch_to_url_change": True,
    }
    await help_setup_mock_config_entry(hass, options)

    with patch(
        "homeassistant.components.camera.Stream.endpoint_url",
        return_value="http://home.assistant/playlist.m3u8",
    ) as mock_request_stream:
        # Request playlist through WebSocket
        client = await hass_ws_client(hass)

        await client.send_json(
            {"id": 3, "type": "camera/stream", "entity_id": "camera.config_test"}
        )
        msg = await client.receive_json()

        # Assert the websocket error message
        assert mock_request_stream.call_count == 0
        assert msg["id"] == 3
        assert msg["type"] == TYPE_RESULT
        assert msg["success"] is False
        assert msg["error"] == {
            "code": "start_stream_failed",
            "message": "camera.config_test does not support play stream service",
        }


@respx.mock
async def test_camera_content_type(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fakeimgbytes_svg,
    fakeimgbytes_jpg,
) -> None:
    """Test generic camera with custom content_type."""
    urlsvg = "https://upload.wikimedia.org/wikipedia/commons/0/02/SVG_logo.svg"
    respx.get(urlsvg).respond(stream=fakeimgbytes_svg)
    urljpg = "https://upload.wikimedia.org/wikipedia/commons/0/0e/Felis_silvestris_silvestris.jpg"
    respx.get(urljpg).respond(stream=fakeimgbytes_jpg)
    cam_config_svg = {
        "name": "config_test_svg",
        "platform": "generic",
        "still_image_url": urlsvg,
        "content_type": "image/svg+xml",
        "limit_refetch_to_url_change": False,
        "framerate": 2,
        "verify_ssl": True,
    }
    cam_config_jpg = {
        "name": "config_test_jpg",
        "platform": "generic",
        "still_image_url": urljpg,
        "content_type": "image/jpeg",
        "limit_refetch_to_url_change": False,
        "framerate": 2,
        "verify_ssl": True,
    }
    await help_setup_mock_config_entry(hass, cam_config_jpg, unique_id=12345)
    await help_setup_mock_config_entry(hass, cam_config_svg, unique_id=54321)

    client = await hass_client()

    resp_1 = await client.get("/api/camera_proxy/camera.config_test_svg")
    assert respx.calls.call_count == 1
    assert resp_1.status == HTTPStatus.OK
    assert resp_1.content_type == "image/svg+xml"
    body = await resp_1.read()
    assert body == fakeimgbytes_svg

    resp_2 = await client.get("/api/camera_proxy/camera.config_test_jpg")
    assert respx.calls.call_count == 2
    assert resp_2.status == HTTPStatus.OK
    assert resp_2.content_type == "image/jpeg"
    body = await resp_2.read()
    assert body == fakeimgbytes_jpg


@respx.mock
async def test_timeout_cancelled(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fakeimgbytes_png,
    fakeimgbytes_jpg,
) -> None:
    """Test that timeouts and cancellations return last image."""

    respx.get("http://example.com").respond(stream=fakeimgbytes_png)

    options = {
        "name": "config_test",
        "platform": "generic",
        "still_image_url": "http://example.com",
        "username": "user",
        "password": "pass",
        "framerate": 20,
    }
    await help_setup_mock_config_entry(hass, options)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == HTTPStatus.OK
    assert respx.calls.call_count == 1
    assert await resp.read() == fakeimgbytes_png

    respx.get("http://example.com").respond(stream=fakeimgbytes_jpg)

    with patch(
        "homeassistant.components.generic.camera.GenericCamera.async_camera_image",
        side_effect=asyncio.CancelledError(),
    ):
        resp = await client.get("/api/camera_proxy/camera.config_test")
        assert respx.calls.call_count == 1
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR

    respx.get("http://example.com").side_effect = [
        httpx.RequestError,
        httpx.TimeoutException,
    ]

    for total_calls in range(2, 4):
        # sleep .1 seconds to make cached image expire
        await asyncio.sleep(0.1)
        resp = await client.get("/api/camera_proxy/camera.config_test")
        assert respx.calls.call_count == total_calls
        assert resp.status == HTTPStatus.OK
        assert await resp.read() == fakeimgbytes_png


async def test_frame_interval_property(hass: HomeAssistant) -> None:
    """Test that the frame interval is calculated and returned correctly."""

    options = {
        "name": "config_test",
        "platform": "generic",
        "stream_source": "rtsp://example.com:554/rtsp/",
        "framerate": 5,
    }
    await help_setup_mock_config_entry(hass, options)

    request = Mock()
    with patch(
        "homeassistant.components.camera.async_get_still_stream"
    ) as mock_get_stream:
        await async_get_mjpeg_stream(hass, request, "camera.config_test")

    assert mock_get_stream.call_args_list[0][0][3] == pytest.approx(0.2)
