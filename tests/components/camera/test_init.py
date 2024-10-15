"""The tests for the camera component."""

from collections.abc import Generator
from http import HTTPStatus
import io
from types import ModuleType
from unittest.mock import AsyncMock, Mock, PropertyMock, mock_open, patch

import pytest

from homeassistant.components import camera
from homeassistant.components.camera.const import (
    DOMAIN,
    PREF_ORIENTATION,
    PREF_PRELOAD_STREAM,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import EMPTY_8_6_JPEG, STREAM_SOURCE, WEBRTC_ANSWER, mock_turbo_jpeg

from tests.common import (
    async_fire_time_changed,
    help_test_all,
    import_and_test_deprecated_constant_enum,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator

HLS_STREAM_SOURCE = "http://127.0.0.1/example.m3u"
WEBRTC_OFFER = "v=0\r\n"


@pytest.fixture(name="image_mock_url")
async def image_mock_url_fixture(hass: HomeAssistant) -> None:
    """Fixture for get_image tests."""
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()


@pytest.fixture(name="mock_hls_stream_source")
async def mock_hls_stream_source_fixture() -> Generator[AsyncMock]:
    """Fixture to create an HLS stream source."""
    with patch(
        "homeassistant.components.camera.Camera.stream_source",
        return_value=HLS_STREAM_SOURCE,
    ) as mock_hls_stream_source:
        yield mock_hls_stream_source


async def provide_web_rtc_answer(stream_source: str, offer: str, stream_id: str) -> str:
    """Simulate an rtsp to webrtc provider."""
    assert stream_source == STREAM_SOURCE
    assert offer == WEBRTC_OFFER
    return WEBRTC_ANSWER


@pytest.fixture(name="mock_rtsp_to_web_rtc")
def mock_rtsp_to_web_rtc_fixture(hass: HomeAssistant) -> Generator[Mock]:
    """Fixture that registers a mock rtsp to web_rtc provider."""
    mock_provider = Mock(side_effect=provide_web_rtc_answer)
    unsub = camera.async_register_rtsp_to_web_rtc_provider(
        hass, "mock_domain", mock_provider
    )
    yield mock_provider
    unsub()


@pytest.mark.usefixtures("image_mock_url")
async def test_get_image_from_camera(hass: HomeAssistant) -> None:
    """Grab an image from camera entity."""

    with patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        autospec=True,
        return_value=b"Test",
    ) as mock_camera:
        image = await camera.async_get_image(hass, "camera.demo_camera")

    assert mock_camera.called
    assert image.content == b"Test"


@pytest.mark.usefixtures("image_mock_url")
async def test_get_image_from_camera_with_width_height(hass: HomeAssistant) -> None:
    """Grab an image from camera entity with width and height."""

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=300, second_height=200
    )
    with (
        patch(
            "homeassistant.components.camera.img_util.TurboJPEGSingleton.instance",
            return_value=turbo_jpeg,
        ),
        patch(
            "homeassistant.components.demo.camera.Path.read_bytes",
            autospec=True,
            return_value=b"Test",
        ) as mock_camera,
    ):
        image = await camera.async_get_image(
            hass, "camera.demo_camera", width=640, height=480
        )

    assert mock_camera.called
    assert image.content == b"Test"


@pytest.mark.usefixtures("image_mock_url")
async def test_get_image_from_camera_with_width_height_scaled(
    hass: HomeAssistant,
) -> None:
    """Grab an image from camera entity with width and height and scale it."""

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=300, second_height=200
    )
    with (
        patch(
            "homeassistant.components.camera.img_util.TurboJPEGSingleton.instance",
            return_value=turbo_jpeg,
        ),
        patch(
            "homeassistant.components.demo.camera.Path.read_bytes",
            autospec=True,
            return_value=b"Valid jpeg",
        ) as mock_camera,
    ):
        image = await camera.async_get_image(
            hass, "camera.demo_camera", width=4, height=3
        )

    assert mock_camera.called
    assert image.content_type == "image/jpg"
    assert image.content == EMPTY_8_6_JPEG


@pytest.mark.usefixtures("image_mock_url")
async def test_get_image_from_camera_not_jpeg(hass: HomeAssistant) -> None:
    """Grab an image from camera entity that we cannot scale."""

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=300, second_height=200
    )
    with (
        patch(
            "homeassistant.components.camera.img_util.TurboJPEGSingleton.instance",
            return_value=turbo_jpeg,
        ),
        patch(
            "homeassistant.components.demo.camera.Path.read_bytes",
            autospec=True,
            return_value=b"png",
        ) as mock_camera,
    ):
        image = await camera.async_get_image(
            hass, "camera.demo_camera_png", width=4, height=3
        )

    assert mock_camera.called
    assert image.content_type == "image/png"
    assert image.content == b"png"


@pytest.mark.usefixtures("mock_camera")
async def test_get_stream_source_from_camera(
    hass: HomeAssistant, mock_stream_source: AsyncMock
) -> None:
    """Fetch stream source from camera entity."""

    stream_source = await camera.async_get_stream_source(hass, "camera.demo_camera")

    assert mock_stream_source.called
    assert stream_source == STREAM_SOURCE


@pytest.mark.usefixtures("image_mock_url")
async def test_get_image_without_exists_camera(hass: HomeAssistant) -> None:
    """Try to get image without exists camera."""
    with (
        patch(
            "homeassistant.helpers.entity_component.EntityComponent.get_entity",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await camera.async_get_image(hass, "camera.demo_camera")


@pytest.mark.usefixtures("image_mock_url")
async def test_get_image_with_timeout(hass: HomeAssistant) -> None:
    """Try to get image with timeout."""
    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.async_camera_image",
            side_effect=TimeoutError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await camera.async_get_image(hass, "camera.demo_camera")


@pytest.mark.usefixtures("image_mock_url")
async def test_get_image_fails(hass: HomeAssistant) -> None:
    """Try to get image with timeout."""
    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.async_camera_image",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await camera.async_get_image(hass, "camera.demo_camera")


@pytest.mark.usefixtures("mock_camera")
async def test_snapshot_service(hass: HomeAssistant) -> None:
    """Test snapshot service."""
    mopen = mock_open()

    with (
        patch("homeassistant.components.camera.open", mopen, create=True),
        patch(
            "homeassistant.components.camera.os.makedirs",
        ),
        patch.object(hass.config, "is_allowed_path", return_value=True),
    ):
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_SNAPSHOT,
            {
                ATTR_ENTITY_ID: "camera.demo_camera",
                camera.ATTR_FILENAME: "/test/snapshot.jpg",
            },
            blocking=True,
        )

        mock_write = mopen().write

        assert len(mock_write.mock_calls) == 1
        assert mock_write.mock_calls[0][1][0] == b"Test"


@pytest.mark.usefixtures("mock_camera")
async def test_snapshot_service_not_allowed_path(hass: HomeAssistant) -> None:
    """Test snapshot service with a not allowed path."""
    mopen = mock_open()

    with (
        patch("homeassistant.components.camera.open", mopen, create=True),
        patch(
            "homeassistant.components.camera.os.makedirs",
        ),
        pytest.raises(HomeAssistantError, match="/test/snapshot.jpg"),
    ):
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_SNAPSHOT,
            {
                ATTR_ENTITY_ID: "camera.demo_camera",
                camera.ATTR_FILENAME: "/test/snapshot.jpg",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_camera", "mock_stream")
async def test_websocket_stream_no_source(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test camera/stream websocket command with camera with no source."""
    await async_setup_component(hass, "camera", {})

    # Request playlist through WebSocket
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 6, "type": "camera/stream", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]


@pytest.mark.usefixtures("mock_camera", "mock_stream")
async def test_websocket_camera_stream(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test camera/stream websocket command."""
    await async_setup_component(hass, "camera", {})

    with (
        patch(
            "homeassistant.components.camera.Stream.endpoint_url",
            return_value="http://home.assistant/playlist.m3u8",
        ) as mock_stream_view_url,
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="http://example.com",
        ),
    ):
        # Request playlist through WebSocket
        client = await hass_ws_client(hass)
        await client.send_json(
            {"id": 6, "type": "camera/stream", "entity_id": "camera.demo_camera"}
        )
        msg = await client.receive_json()

        # Assert WebSocket response
        assert mock_stream_view_url.called
        assert msg["id"] == 6
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        assert msg["result"]["url"][-13:] == "playlist.m3u8"


@pytest.mark.usefixtures("mock_camera")
async def test_websocket_get_prefs(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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


@pytest.mark.usefixtures("mock_camera")
async def test_websocket_update_preload_prefs(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test updating camera preferences."""

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 7, "type": "camera/get_prefs", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # The default prefs should be returned. Preload stream should be False
    assert msg["success"]
    assert msg["result"][PREF_PRELOAD_STREAM] is False

    # Update the preference
    await client.send_json(
        {
            "id": 8,
            "type": "camera/update_prefs",
            "entity_id": "camera.demo_camera",
            "preload_stream": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"][PREF_PRELOAD_STREAM] is True

    # Check that the preference was saved
    await client.send_json(
        {"id": 9, "type": "camera/get_prefs", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()
    # preload_stream entry for this camera should have been added
    assert msg["result"][PREF_PRELOAD_STREAM] is True


@pytest.mark.usefixtures("mock_camera")
async def test_websocket_update_orientation_prefs(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test updating camera preferences."""
    await async_setup_component(hass, "homeassistant", {})

    client = await hass_ws_client(hass)

    # Try sending orientation update for entity not in entity registry
    await client.send_json(
        {
            "id": 10,
            "type": "camera/update_prefs",
            "entity_id": "camera.demo_uniquecamera",
            "orientation": 3,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "update_failed"

    assert not entity_registry.async_get("camera.demo_uniquecamera")
    # Since we don't have a unique id, we need to create a registry entry
    entity_registry.async_get_or_create(DOMAIN, "demo", "uniquecamera")
    entity_registry.async_update_entity_options(
        "camera.demo_uniquecamera",
        DOMAIN,
        {},
    )

    await client.send_json(
        {
            "id": 11,
            "type": "camera/update_prefs",
            "entity_id": "camera.demo_uniquecamera",
            "orientation": 3,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    er_camera_prefs = entity_registry.async_get("camera.demo_uniquecamera").options[
        DOMAIN
    ]
    assert er_camera_prefs[PREF_ORIENTATION] == camera.Orientation.ROTATE_180
    assert response["result"][PREF_ORIENTATION] == er_camera_prefs[PREF_ORIENTATION]
    # Check that the preference was saved
    await client.send_json(
        {"id": 12, "type": "camera/get_prefs", "entity_id": "camera.demo_uniquecamera"}
    )
    msg = await client.receive_json()
    # orientation entry for this camera should have been added
    assert msg["result"]["orientation"] == camera.Orientation.ROTATE_180


@pytest.mark.usefixtures("mock_camera", "mock_stream")
async def test_play_stream_service_no_source(hass: HomeAssistant) -> None:
    """Test camera play_stream service."""
    data = {
        ATTR_ENTITY_ID: "camera.demo_camera",
        camera.ATTR_MEDIA_PLAYER: "media_player.test",
    }
    with pytest.raises(HomeAssistantError):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN, camera.SERVICE_PLAY_STREAM, data, blocking=True
        )


@pytest.mark.usefixtures("mock_camera", "mock_stream")
async def test_handle_play_stream_service(hass: HomeAssistant) -> None:
    """Test camera play_stream service."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    await async_setup_component(hass, "media_player", {})
    with (
        patch(
            "homeassistant.components.camera.Stream.endpoint_url",
        ) as mock_request_stream,
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="http://example.com",
        ),
    ):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_PLAY_STREAM,
            {
                ATTR_ENTITY_ID: "camera.demo_camera",
                camera.ATTR_MEDIA_PLAYER: "media_player.test",
            },
            blocking=True,
        )
        # So long as we request the stream, the rest should be covered
        # by the play_media service tests.
        assert mock_request_stream.called


@pytest.mark.usefixtures("mock_stream")
async def test_no_preload_stream(hass: HomeAssistant) -> None:
    """Test camera preload preference."""
    demo_settings = camera.DynamicStreamSettings()
    with (
        patch(
            "homeassistant.components.camera.Stream.endpoint_url",
        ) as mock_request_stream,
        patch(
            "homeassistant.components.camera.prefs.CameraPreferences.get_dynamic_stream_settings",
            return_value=demo_settings,
        ),
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            new_callable=PropertyMock,
        ) as mock_stream_source,
    ):
        mock_stream_source.return_value = io.BytesIO()
        await async_setup_component(hass, "camera", {DOMAIN: {"platform": "demo"}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert not mock_request_stream.called


@pytest.mark.usefixtures("mock_stream")
async def test_preload_stream(hass: HomeAssistant) -> None:
    """Test camera preload preference."""
    demo_settings = camera.DynamicStreamSettings(preload_stream=True)
    with (
        patch("homeassistant.components.camera.create_stream") as mock_create_stream,
        patch(
            "homeassistant.components.camera.prefs.CameraPreferences.get_dynamic_stream_settings",
            return_value=demo_settings,
        ),
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="http://example.com",
        ),
    ):
        mock_create_stream.return_value.start = AsyncMock()
        assert await async_setup_component(
            hass, "camera", {DOMAIN: {"platform": "demo"}}
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert mock_create_stream.called


@pytest.mark.usefixtures("mock_camera")
async def test_record_service_invalid_path(hass: HomeAssistant) -> None:
    """Test record service with invalid path."""
    with (
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(HomeAssistantError),
    ):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_RECORD,
            {
                ATTR_ENTITY_ID: "camera.demo_camera",
                camera.CONF_FILENAME: "/my/invalid/path",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_camera", "mock_stream")
async def test_record_service(hass: HomeAssistant) -> None:
    """Test record service."""
    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="http://example.com",
        ),
        patch(
            "homeassistant.components.stream.Stream.async_record",
            autospec=True,
        ) as mock_record,
    ):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_RECORD,
            {ATTR_ENTITY_ID: "camera.demo_camera", camera.CONF_FILENAME: "/my/path"},
            blocking=True,
        )
        # So long as we call stream.record, the rest should be covered
        # by those tests.
        assert mock_record.called


@pytest.mark.usefixtures("mock_camera")
async def test_camera_proxy_stream(hass_client: ClientSessionGenerator) -> None:
    """Test record service."""

    client = await hass_client()

    async with client.get("/api/camera_proxy_stream/camera.demo_camera") as response:
        assert response.status == HTTPStatus.OK

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.handle_async_mjpeg_stream",
        return_value=None,
    ):
        async with await client.get(
            "/api/camera_proxy_stream/camera.demo_camera"
        ) as response:
            assert response.status == HTTPStatus.BAD_GATEWAY


@pytest.mark.usefixtures("mock_camera_web_rtc")
async def test_websocket_web_rtc_offer(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test initiating a WebRTC stream with offer and answer."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    assert response["result"]["answer"] == WEBRTC_ANSWER


@pytest.mark.usefixtures("mock_camera_web_rtc")
async def test_websocket_web_rtc_offer_invalid_entity(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC with a camera entity that does not exist."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.does_not_exist",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]


@pytest.mark.usefixtures("mock_camera_web_rtc")
async def test_websocket_web_rtc_offer_missing_offer(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC stream with missing required fields."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.usefixtures("mock_camera_web_rtc")
async def test_websocket_web_rtc_offer_failure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC stream that fails handling the offer."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        side_effect=HomeAssistantError("offer failed"),
    ):
        await client.send_json(
            {
                "id": 9,
                "type": "camera/web_rtc_offer",
                "entity_id": "camera.demo_camera",
                "offer": WEBRTC_OFFER,
            }
        )
        response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "web_rtc_offer_failed"
    assert response["error"]["message"] == "offer failed"


@pytest.mark.usefixtures("mock_camera_web_rtc")
async def test_websocket_web_rtc_offer_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC stream with timeout handling the offer."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        side_effect=TimeoutError(),
    ):
        await client.send_json(
            {
                "id": 9,
                "type": "camera/web_rtc_offer",
                "entity_id": "camera.demo_camera",
                "offer": WEBRTC_OFFER,
            }
        )
        response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "web_rtc_offer_failed"
    assert response["error"]["message"] == "Timeout handling WebRTC offer"


@pytest.mark.usefixtures("mock_camera")
async def test_websocket_web_rtc_offer_invalid_stream_type(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC initiating for a camera with a different stream_type."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "web_rtc_offer_failed"


@pytest.mark.usefixtures("mock_camera")
async def test_state_streaming(hass: HomeAssistant) -> None:
    """Camera state."""
    demo_camera = hass.states.get("camera.demo_camera")
    assert demo_camera is not None
    assert demo_camera.state == camera.CameraState.STREAMING


@pytest.mark.usefixtures("mock_camera", "mock_stream")
async def test_stream_unavailable(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Camera state."""
    await async_setup_component(hass, "camera", {})

    with (
        patch(
            "homeassistant.components.camera.Stream.endpoint_url",
            return_value="http://home.assistant/playlist.m3u8",
        ),
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="http://example.com",
        ),
        patch(
            "homeassistant.components.camera.Stream.set_update_callback",
        ) as mock_update_callback,
    ):
        # Request playlist through WebSocket. We just want to create the stream
        # but don't care about the result.
        client = await hass_ws_client(hass)
        await client.send_json(
            {"id": 10, "type": "camera/stream", "entity_id": "camera.demo_camera"}
        )
        await client.receive_json()
        assert mock_update_callback.called

    # Simulate the stream going unavailable
    callback = mock_update_callback.call_args.args[0]
    with patch(
        "homeassistant.components.camera.Stream.available", new_callable=lambda: False
    ):
        callback()
        await hass.async_block_till_done()

    demo_camera = hass.states.get("camera.demo_camera")
    assert demo_camera is not None
    assert demo_camera.state == STATE_UNAVAILABLE

    # Simulate stream becomes available
    with patch(
        "homeassistant.components.camera.Stream.available", new_callable=lambda: True
    ):
        callback()
        await hass.async_block_till_done()

    demo_camera = hass.states.get("camera.demo_camera")
    assert demo_camera is not None
    assert demo_camera.state == camera.CameraState.STREAMING


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_rtsp_to_web_rtc_offer(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_rtsp_to_web_rtc: Mock,
) -> None:
    """Test creating a web_rtc offer from an rstp provider."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response.get("id") == 9
    assert response.get("type") == TYPE_RESULT
    assert response.get("success")
    assert "result" in response
    assert response["result"] == {"answer": WEBRTC_ANSWER}

    assert mock_rtsp_to_web_rtc.called


@pytest.mark.usefixtures(
    "mock_camera",
    "mock_hls_stream_source",  # Not an RTSP stream source
    "mock_rtsp_to_web_rtc",
)
async def test_unsupported_rtsp_to_web_rtc_stream_type(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test rtsp-to-webrtc is not registered for non-RTSP streams."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 10,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response.get("id") == 10
    assert response.get("type") == TYPE_RESULT
    assert "success" in response
    assert not response["success"]


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_rtsp_to_web_rtc_provider_unregistered(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test creating a web_rtc offer from an rstp provider."""
    mock_provider = Mock(side_effect=provide_web_rtc_answer)
    unsub = camera.async_register_rtsp_to_web_rtc_provider(
        hass, "mock_domain", mock_provider
    )

    client = await hass_ws_client(hass)

    # Registered provider can handle the WebRTC offer
    await client.send_json(
        {
            "id": 11,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response["id"] == 11
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    assert response["result"]["answer"] == WEBRTC_ANSWER

    assert mock_provider.called
    mock_provider.reset_mock()

    # Unregister provider, then verify the WebRTC offer cannot be handled
    unsub()
    await client.send_json(
        {
            "id": 12,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response.get("id") == 12
    assert response.get("type") == TYPE_RESULT
    assert "success" in response
    assert not response["success"]

    assert not mock_provider.called


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_rtsp_to_web_rtc_offer_not_accepted(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a provider that can't satisfy the rtsp to webrtc offer."""

    async def provide_none(stream_source: str, offer: str) -> str:
        """Simulate a provider that can't accept the offer."""
        return None

    mock_provider = Mock(side_effect=provide_none)
    unsub = camera.async_register_rtsp_to_web_rtc_provider(
        hass, "mock_domain", mock_provider
    )
    client = await hass_ws_client(hass)

    # Registered provider can handle the WebRTC offer
    await client.send_json(
        {
            "id": 11,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response["id"] == 11
    assert response.get("type") == TYPE_RESULT
    assert "success" in response
    assert not response["success"]

    assert mock_provider.called

    unsub()


@pytest.mark.usefixtures("mock_camera")
async def test_use_stream_for_stills(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the component can grab images from stream."""

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value=None,
        ) as mock_stream_source,
        patch(
            "homeassistant.components.demo.camera.DemoCamera.use_stream_for_stills",
            return_value=True,
        ),
    ):
        # First test when the integration does not support stream should fail
        resp = await client.get("/api/camera_proxy/camera.demo_camera_without_stream")
        await hass.async_block_till_done()
        mock_stream_source.assert_not_called()
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
        # Test when the integration does not provide a stream_source should fail
        resp = await client.get("/api/camera_proxy/camera.demo_camera")
        await hass.async_block_till_done()
        mock_stream_source.assert_called_once()
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="rtsp://some_source",
        ) as mock_stream_source,
        patch("homeassistant.components.camera.create_stream") as mock_create_stream,
        patch(
            "homeassistant.components.demo.camera.DemoCamera.use_stream_for_stills",
            return_value=True,
        ),
    ):
        # Now test when creating the stream succeeds
        mock_stream = Mock()
        mock_stream.async_get_image = AsyncMock()
        mock_stream.async_get_image.return_value = b"stream_keyframe_image"
        mock_create_stream.return_value = mock_stream

        # should start the stream and get the image
        resp = await client.get("/api/camera_proxy/camera.demo_camera")
        await hass.async_block_till_done()
        mock_create_stream.assert_called_once()
        mock_stream.async_get_image.assert_called_once()
        assert resp.status == HTTPStatus.OK
        assert await resp.read() == b"stream_keyframe_image"


@pytest.mark.parametrize(
    "module",
    [camera, camera.const],
)
def test_all(module: ModuleType) -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(module)


@pytest.mark.parametrize(
    "enum",
    list(camera.const.StreamType),
)
@pytest.mark.parametrize(
    "module",
    [camera, camera.const],
)
def test_deprecated_stream_type_constants(
    caplog: pytest.LogCaptureFixture,
    enum: camera.const.StreamType,
    module: ModuleType,
) -> None:
    """Test deprecated stream type constants."""
    import_and_test_deprecated_constant_enum(
        caplog, module, enum, "STREAM_TYPE_", "2025.1"
    )


@pytest.mark.parametrize(
    "enum",
    list(camera.const.CameraState),
)
@pytest.mark.parametrize(
    "module",
    [camera],
)
def test_deprecated_state_constants(
    caplog: pytest.LogCaptureFixture,
    enum: camera.const.StreamType,
    module: ModuleType,
) -> None:
    """Test deprecated stream type constants."""
    import_and_test_deprecated_constant_enum(caplog, module, enum, "STATE_", "2025.10")


@pytest.mark.parametrize(
    "entity_feature",
    list(camera.CameraEntityFeature),
)
def test_deprecated_support_constants(
    caplog: pytest.LogCaptureFixture,
    entity_feature: camera.CameraEntityFeature,
) -> None:
    """Test deprecated support constants."""
    import_and_test_deprecated_constant_enum(
        caplog, camera, entity_feature, "SUPPORT_", "2025.1"
    )


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockCamera(camera.Camera):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return 1

    entity = MockCamera()
    assert entity.supported_features_compat is camera.CameraEntityFeature(1)
    assert "MockCamera" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "CameraEntityFeature.ON_OFF" in caplog.text
    caplog.clear()
    assert entity.supported_features_compat is camera.CameraEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text


@pytest.mark.usefixtures("mock_camera")
async def test_entity_picture_url_changes_on_token_update(hass: HomeAssistant) -> None:
    """Test the token is rotated and entity entity picture cache is cleared."""
    await async_setup_component(hass, "camera", {})
    await hass.async_block_till_done()

    camera_state = hass.states.get("camera.demo_camera")
    original_picture = camera_state.attributes["entity_picture"]
    assert "token=" in original_picture

    async_fire_time_changed(hass, dt_util.utcnow() + camera.TOKEN_CHANGE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    camera_state = hass.states.get("camera.demo_camera")
    new_entity_picture = camera_state.attributes["entity_picture"]
    assert new_entity_picture != original_picture
    assert "token=" in new_entity_picture
