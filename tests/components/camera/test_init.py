"""The tests for the camera component."""
import asyncio
import base64
import io
from unittest.mock import PropertyMock, mock_open, patch

import pytest

from homeassistant.components import camera
from homeassistant.components.camera.const import DOMAIN, PREF_PRELOAD_STREAM
from homeassistant.components.camera.prefs import CameraEntityPreferences
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import mock_coro
from tests.components.camera import common


@pytest.fixture
def mock_camera(hass):
    """Initialize a demo camera platform."""
    assert hass.loop.run_until_complete(
        async_setup_component(hass, "camera", {camera.DOMAIN: {"platform": "demo"}})
    )

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.camera_image",
        return_value=b"Test",
    ):
        yield


@pytest.fixture
def mock_stream(hass):
    """Initialize a demo camera platform with streaming."""
    assert hass.loop.run_until_complete(
        async_setup_component(hass, "stream", {"stream": {}})
    )


@pytest.fixture
def setup_camera_prefs(hass):
    """Initialize HTTP API."""
    return common.mock_camera_prefs(hass, "camera.demo_camera")


@pytest.fixture
async def image_mock_url(hass):
    """Fixture for get_image tests."""
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )


async def test_get_image_from_camera(hass, image_mock_url):
    """Grab an image from camera entity."""

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.camera_image",
        autospec=True,
        return_value=b"Test",
    ) as mock_camera:
        image = await camera.async_get_image(hass, "camera.demo_camera")

    assert mock_camera.called
    assert image.content == b"Test"


async def test_get_image_without_exists_camera(hass, image_mock_url):
    """Try to get image without exists camera."""
    with patch(
        "homeassistant.helpers.entity_component.EntityComponent.get_entity",
        return_value=None,
    ), pytest.raises(HomeAssistantError):
        await camera.async_get_image(hass, "camera.demo_camera")


async def test_get_image_with_timeout(hass, image_mock_url):
    """Try to get image with timeout."""
    with patch(
        "homeassistant.components.camera.Camera.async_camera_image",
        side_effect=asyncio.TimeoutError,
    ), pytest.raises(HomeAssistantError):
        await camera.async_get_image(hass, "camera.demo_camera")


async def test_get_image_fails(hass, image_mock_url):
    """Try to get image with timeout."""
    with patch(
        "homeassistant.components.camera.Camera.async_camera_image",
        return_value=mock_coro(None),
    ), pytest.raises(HomeAssistantError):
        await camera.async_get_image(hass, "camera.demo_camera")


async def test_snapshot_service(hass, mock_camera):
    """Test snapshot service."""
    mopen = mock_open()

    with patch(
        "homeassistant.components.camera.open", mopen, create=True
    ), patch.object(hass.config, "is_allowed_path", return_value=True):
        common.async_snapshot(hass, "/test/snapshot.jpg")
        await hass.async_block_till_done()

        mock_write = mopen().write

        assert len(mock_write.mock_calls) == 1
        assert mock_write.mock_calls[0][1][0] == b"Test"


async def test_websocket_camera_thumbnail(hass, hass_ws_client, mock_camera):
    """Test camera_thumbnail websocket command."""
    await async_setup_component(hass, "camera", {})

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "camera_thumbnail", "entity_id": "camera.demo_camera"}
    )

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["content_type"] == "image/jpeg"
    assert msg["result"]["content"] == base64.b64encode(b"Test").decode("utf-8")


async def test_websocket_stream_no_source(
    hass, hass_ws_client, mock_camera, mock_stream
):
    """Test camera/stream websocket command."""
    await async_setup_component(hass, "camera", {})

    with patch(
        "homeassistant.components.camera.request_stream",
        return_value="http://home.assistant/playlist.m3u8",
    ) as mock_request_stream:
        # Request playlist through WebSocket
        client = await hass_ws_client(hass)
        await client.send_json(
            {"id": 6, "type": "camera/stream", "entity_id": "camera.demo_camera"}
        )
        msg = await client.receive_json()

        # Assert WebSocket response
        assert not mock_request_stream.called
        assert msg["id"] == 6
        assert msg["type"] == TYPE_RESULT
        assert not msg["success"]


async def test_websocket_camera_stream(hass, hass_ws_client, mock_camera, mock_stream):
    """Test camera/stream websocket command."""
    await async_setup_component(hass, "camera", {})

    with patch(
        "homeassistant.components.camera.request_stream",
        return_value="http://home.assistant/playlist.m3u8",
    ) as mock_request_stream, patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=mock_coro("http://example.com"),
    ):
        # Request playlist through WebSocket
        client = await hass_ws_client(hass)
        await client.send_json(
            {"id": 6, "type": "camera/stream", "entity_id": "camera.demo_camera"}
        )
        msg = await client.receive_json()

        # Assert WebSocket response
        assert mock_request_stream.called
        assert msg["id"] == 6
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        assert msg["result"]["url"][-13:] == "playlist.m3u8"


async def test_websocket_get_prefs(hass, hass_ws_client, mock_camera):
    """Test get camera preferences websocket command."""
    await async_setup_component(hass, "camera", {})

    # Request preferences through websocket
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 7, "type": "camera/get_prefs", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["success"]


async def test_websocket_update_prefs(
    hass, hass_ws_client, mock_camera, setup_camera_prefs
):
    """Test updating preference."""
    await async_setup_component(hass, "camera", {})
    assert setup_camera_prefs[PREF_PRELOAD_STREAM]
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 8,
            "type": "camera/update_prefs",
            "entity_id": "camera.demo_camera",
            "preload_stream": False,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert not setup_camera_prefs[PREF_PRELOAD_STREAM]
    assert (
        response["result"][PREF_PRELOAD_STREAM]
        == setup_camera_prefs[PREF_PRELOAD_STREAM]
    )


async def test_play_stream_service_no_source(hass, mock_camera, mock_stream):
    """Test camera play_stream service."""
    data = {
        ATTR_ENTITY_ID: "camera.demo_camera",
        camera.ATTR_MEDIA_PLAYER: "media_player.test",
    }
    with patch("homeassistant.components.camera.request_stream"), pytest.raises(
        HomeAssistantError
    ):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN, camera.SERVICE_PLAY_STREAM, data, blocking=True
        )


async def test_handle_play_stream_service(hass, mock_camera, mock_stream):
    """Test camera play_stream service."""
    await async_setup_component(hass, "media_player", {})
    data = {
        ATTR_ENTITY_ID: "camera.demo_camera",
        camera.ATTR_MEDIA_PLAYER: "media_player.test",
    }
    with patch(
        "homeassistant.components.camera.request_stream"
    ) as mock_request_stream, patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=mock_coro("http://example.com"),
    ):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN, camera.SERVICE_PLAY_STREAM, data, blocking=True
        )
        # So long as we request the stream, the rest should be covered
        # by the play_media service tests.
        assert mock_request_stream.called


async def test_no_preload_stream(hass, mock_stream):
    """Test camera preload preference."""
    demo_prefs = CameraEntityPreferences({PREF_PRELOAD_STREAM: False})
    with patch(
        "homeassistant.components.camera.request_stream"
    ) as mock_request_stream, patch(
        "homeassistant.components.camera.prefs.CameraPreferences.get",
        return_value=demo_prefs,
    ), patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        new_callable=PropertyMock,
    ) as mock_stream_source:
        mock_stream_source.return_value = io.BytesIO()
        await async_setup_component(hass, "camera", {DOMAIN: {"platform": "demo"}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert not mock_request_stream.called


async def test_preload_stream(hass, mock_stream):
    """Test camera preload preference."""
    demo_prefs = CameraEntityPreferences({PREF_PRELOAD_STREAM: True})
    with patch(
        "homeassistant.components.camera.request_stream"
    ) as mock_request_stream, patch(
        "homeassistant.components.camera.prefs.CameraPreferences.get",
        return_value=demo_prefs,
    ), patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=mock_coro("http://example.com"),
    ):
        await async_setup_component(hass, "camera", {DOMAIN: {"platform": "demo"}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert mock_request_stream.called


async def test_record_service_invalid_path(hass, mock_camera):
    """Test record service with invalid path."""
    data = {
        ATTR_ENTITY_ID: "camera.demo_camera",
        camera.CONF_FILENAME: "/my/invalid/path",
    }
    with patch.object(
        hass.config, "is_allowed_path", return_value=False
    ), pytest.raises(HomeAssistantError):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN, camera.SERVICE_RECORD, data, blocking=True
        )


async def test_record_service(hass, mock_camera, mock_stream):
    """Test record service."""
    data = {ATTR_ENTITY_ID: "camera.demo_camera", camera.CONF_FILENAME: "/my/path"}

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=mock_coro("http://example.com"),
    ), patch(
        "homeassistant.components.stream.async_handle_record_service",
        return_value=mock_coro(),
    ) as mock_record_service, patch.object(
        hass.config, "is_allowed_path", return_value=True
    ):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN, camera.SERVICE_RECORD, data, blocking=True
        )
        # So long as we call stream.record, the rest should be covered
        # by those tests.
        assert mock_record_service.called
