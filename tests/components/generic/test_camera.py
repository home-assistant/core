"""The tests for generic camera component."""
import asyncio
from os import path
from unittest.mock import patch

import httpx
import respx

from homeassistant import config as hass_config
from homeassistant.components.generic import DOMAIN
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    SERVICE_RELOAD,
)
from homeassistant.setup import async_setup_component


@respx.mock
async def test_fetching_url(hass, hass_client):
    """Test that it fetches the given url."""
    respx.get("http://example.com").respond(text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "http://example.com",
                "username": "user",
                "password": "pass",
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 200
    assert respx.calls.call_count == 1
    body = await resp.text()
    assert body == "hello world"

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 2


async def test_fetching_without_verify_ssl(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url when ssl verify is off."""
    aioclient_mock.get("https://example.com", text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "https://example.com",
                "username": "user",
                "password": "pass",
                "verify_ssl": "false",
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 200


async def test_fetching_url_with_verify_ssl(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url when ssl verify is explicitly on."""
    aioclient_mock.get("https://example.com", text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "https://example.com",
                "username": "user",
                "password": "pass",
                "verify_ssl": "true",
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 200


@respx.mock
async def test_limit_refetch(hass, hass_client):
    """Test that it fetches the given url."""
    respx.get("http://example.com/5a").respond(text="hello world")
    respx.get("http://example.com/10a").respond(text="hello world")
    respx.get("http://example.com/15a").respond(text="hello planet")
    respx.get("http://example.com/20a").respond(status_code=HTTP_NOT_FOUND)

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": 'http://example.com/{{ states.sensor.temp.state + "a" }}',
                "limit_refetch_to_url_change": True,
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    hass.states.async_set("sensor.temp", "5")

    with patch("async_timeout.timeout", side_effect=asyncio.TimeoutError()):
        resp = await client.get("/api/camera_proxy/camera.config_test")
        assert respx.calls.call_count == 0
        assert resp.status == HTTP_INTERNAL_SERVER_ERROR

    hass.states.async_set("sensor.temp", "10")

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 1
    assert resp.status == 200
    body = await resp.text()
    assert body == "hello world"

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 1
    assert resp.status == 200
    body = await resp.text()
    assert body == "hello world"

    hass.states.async_set("sensor.temp", "15")

    # Url change = fetch new image
    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 2
    assert resp.status == 200
    body = await resp.text()
    assert body == "hello planet"

    # Cause a template render error
    hass.states.async_remove("sensor.temp")
    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert respx.calls.call_count == 2
    assert resp.status == 200
    body = await resp.text()
    assert body == "hello planet"


async def test_stream_source(aioclient_mock, hass, hass_client, hass_ws_client):
    """Test that the stream source is rendered."""
    assert await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "https://example.com",
                "stream_source": 'http://example.com/{{ states.sensor.temp.state + "a" }}',
                "limit_refetch_to_url_change": True,
            },
        },
    )
    assert await async_setup_component(hass, "stream", {})
    await hass.async_block_till_done()

    hass.states.async_set("sensor.temp", "5")

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


async def test_stream_source_error(aioclient_mock, hass, hass_client, hass_ws_client):
    """Test that the stream source has an error."""
    assert await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "https://example.com",
                # Does not exist
                "stream_source": 'http://example.com/{{ states.sensor.temp.state + "a" }}',
                "limit_refetch_to_url_change": True,
            },
        },
    )
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


async def test_setup_alternative_options(hass, hass_ws_client):
    """Test that the stream source is setup with different config options."""
    assert await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "https://example.com",
                "authentication": "digest",
                "username": "user",
                "password": "pass",
                "stream_source": "rtsp://example.com:554/rtsp/",
                "rtsp_transport": "udp",
            },
        },
    )
    await hass.async_block_till_done()
    assert hass.data["camera"].get_entity("camera.config_test")


async def test_no_stream_source(aioclient_mock, hass, hass_client, hass_ws_client):
    """Test a stream request without stream source option set."""
    assert await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "https://example.com",
                "limit_refetch_to_url_change": True,
            }
        },
    )
    await hass.async_block_till_done()

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
async def test_camera_content_type(hass, hass_client):
    """Test generic camera with custom content_type."""
    svg_image = "<some image>"
    urlsvg = "https://upload.wikimedia.org/wikipedia/commons/0/02/SVG_logo.svg"
    respx.get(urlsvg).respond(text=svg_image)

    cam_config_svg = {
        "name": "config_test_svg",
        "platform": "generic",
        "still_image_url": urlsvg,
        "content_type": "image/svg+xml",
    }
    cam_config_normal = cam_config_svg.copy()
    cam_config_normal.pop("content_type")
    cam_config_normal["name"] = "config_test_jpg"

    await async_setup_component(
        hass, "camera", {"camera": [cam_config_svg, cam_config_normal]}
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp_1 = await client.get("/api/camera_proxy/camera.config_test_svg")
    assert respx.calls.call_count == 1
    assert resp_1.status == 200
    assert resp_1.content_type == "image/svg+xml"
    body = await resp_1.text()
    assert body == svg_image

    resp_2 = await client.get("/api/camera_proxy/camera.config_test_jpg")
    assert respx.calls.call_count == 2
    assert resp_2.status == 200
    assert resp_2.content_type == "image/jpeg"
    body = await resp_2.text()
    assert body == svg_image


@respx.mock
async def test_reloading(hass, hass_client):
    """Test we can cleanly reload."""
    respx.get("http://example.com").respond(text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "http://example.com",
                "username": "user",
                "password": "pass",
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 200
    assert respx.calls.call_count == 1
    body = await resp.text()
    assert body == "hello world"

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "generic/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 404

    resp = await client.get("/api/camera_proxy/camera.reload")

    assert resp.status == 200
    assert respx.calls.call_count == 2
    body = await resp.text()
    assert body == "hello world"


@respx.mock
async def test_timeout_cancelled(hass, hass_client):
    """Test that timeouts and cancellations return last image."""

    respx.get("http://example.com").respond(text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "generic",
                "still_image_url": "http://example.com",
                "username": "user",
                "password": "pass",
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 200
    assert respx.calls.call_count == 1
    assert await resp.text() == "hello world"

    respx.get("http://example.com").respond(text="not hello world")

    with patch(
        "homeassistant.components.generic.camera.GenericCamera._async_camera_image",
        side_effect=asyncio.CancelledError(),
    ):
        resp = await client.get("/api/camera_proxy/camera.config_test")
        assert respx.calls.call_count == 1
        assert resp.status == 500

    respx.get("http://example.com").side_effect = [
        httpx.RequestError,
        httpx.TimeoutException,
    ]

    for total_calls in range(2, 4):
        resp = await client.get("/api/camera_proxy/camera.config_test")
        assert respx.calls.call_count == total_calls
        assert resp.status == 200
        assert await resp.text() == "hello world"


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
