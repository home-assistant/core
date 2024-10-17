"""Test camera WebRTC."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.camera import Camera
from homeassistant.components.camera.const import StreamType
from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.components.camera.webrtc import (
    DATA_ICE_SERVERS,
    CameraWebRTCProvider,
    RTCIceServer,
    async_register_rtsp_to_web_rtc_provider,
    async_register_webrtc_provider,
    register_ice_server,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import STREAM_SOURCE, WEBRTC_ANSWER

from tests.typing import WebSocketGenerator

WEBRTC_OFFER = "v=0\r\n"
HLS_STREAM_SOURCE = "http://127.0.0.1/example.m3u"


@pytest.mark.usefixtures("mock_camera", "mock_stream", "mock_stream_source")
async def test_async_register_webrtc_provider(
    hass: HomeAssistant,
) -> None:
    """Test registering a WebRTC provider."""
    await async_setup_component(hass, "camera", {})

    camera = get_camera_from_entity_id(hass, "camera.demo_camera")
    assert camera.frontend_stream_type is StreamType.HLS

    stream_supported = True

    class TestProvider(CameraWebRTCProvider):
        """Test provider."""

        def async_is_supported(self, stream_source: str) -> bool:
            """Determine if the provider supports the stream source."""
            nonlocal stream_supported
            return stream_supported

        async def async_handle_webrtc_offer(
            self, camera: Camera, offer_sdp: str
        ) -> str | None:
            """Handle the WebRTC offer and return an answer."""
            return "answer"

    unregister = async_register_webrtc_provider(hass, TestProvider())
    await hass.async_block_till_done()

    assert camera.frontend_stream_type is StreamType.WEB_RTC

    # Mark stream as unsupported
    stream_supported = False
    # Manually refresh the provider
    await camera.async_refresh_providers()

    assert camera.frontend_stream_type is StreamType.HLS

    # Mark stream as unsupported
    stream_supported = True
    # Manually refresh the provider
    await camera.async_refresh_providers()
    assert camera.frontend_stream_type is StreamType.WEB_RTC

    unregister()
    await hass.async_block_till_done()

    assert camera.frontend_stream_type is StreamType.HLS


@pytest.mark.usefixtures("mock_camera", "mock_stream", "mock_stream_source")
async def test_async_register_webrtc_provider_twice(
    hass: HomeAssistant,
) -> None:
    """Test registering a WebRTC provider twice should raise."""
    await async_setup_component(hass, "camera", {})

    class TestProvider(CameraWebRTCProvider):
        """Test provider."""

        def async_is_supported(self, stream_source: str) -> bool:
            """Determine if the provider supports the stream source."""
            return True

        async def async_handle_webrtc_offer(
            self, camera: Camera, offer_sdp: str
        ) -> str | None:
            """Handle the WebRTC offer and return an answer."""
            return "answer"

    provider = TestProvider()
    async_register_webrtc_provider(hass, provider)
    await hass.async_block_till_done()

    with pytest.raises(ValueError, match="Provider already registered"):
        async_register_webrtc_provider(hass, provider)


async def test_async_register_webrtc_provider_camera_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test registering a WebRTC provider when camera is not loaded."""

    class TestProvider(CameraWebRTCProvider):
        """Test provider."""

        def async_is_supported(self, stream_source: str) -> bool:
            """Determine if the provider supports the stream source."""
            return True

        async def async_handle_webrtc_offer(
            self, camera: Camera, offer_sdp: str
        ) -> str | None:
            """Handle the WebRTC offer and return an answer."""
            return "answer"

    with pytest.raises(ValueError, match="Unexpected state, camera not loaded"):
        async_register_webrtc_provider(hass, TestProvider())


@pytest.mark.usefixtures("mock_camera", "mock_stream", "mock_stream_source")
async def test_async_register_ice_server(
    hass: HomeAssistant,
) -> None:
    """Test registering an ICE server."""
    await async_setup_component(hass, "camera", {})

    # Clear any existing ICE servers
    hass.data[DATA_ICE_SERVERS].clear()

    called = 0

    async def get_ice_server() -> RTCIceServer:
        nonlocal called
        called += 1
        return RTCIceServer(urls="stun:example.com")

    unregister = register_ice_server(hass, get_ice_server)
    assert not called

    camera = get_camera_from_entity_id(hass, "camera.demo_camera")
    config = await camera.async_get_webrtc_client_configuration()

    assert config.configuration.ice_servers == [RTCIceServer(urls="stun:example.com")]
    assert called == 1

    # register another ICE server
    called_2 = 0

    async def get_ice_server_2() -> RTCIceServer:
        nonlocal called_2
        called_2 += 1
        return RTCIceServer(
            urls=["stun:example2.com", "turn:example2.com"],
            username="user",
            credential="pass",
        )

    unregister_2 = register_ice_server(hass, get_ice_server_2)

    config = await camera.async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == [
        RTCIceServer(urls="stun:example.com"),
        RTCIceServer(
            urls=["stun:example2.com", "turn:example2.com"],
            username="user",
            credential="pass",
        ),
    ]
    assert called == 2
    assert called_2 == 1

    # unregister the first ICE server

    unregister()

    config = await camera.async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == [
        RTCIceServer(
            urls=["stun:example2.com", "turn:example2.com"],
            username="user",
            credential="pass",
        ),
    ]
    assert called == 2
    assert called_2 == 2

    # unregister the second ICE server
    unregister_2()

    config = await camera.async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == []


@pytest.mark.usefixtures("mock_camera_webrtc")
async def test_ws_get_client_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get WebRTC client config."""
    await async_setup_component(hass, "camera", {})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "camera/webrtc/get_client_config", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "configuration": {
            "iceServers": [{"urls": "stun:stun.home-assistant.io:3478"}],
        },
        "getCandidatesUpfront": False,
    }

    async def get_ice_server() -> RTCIceServer:
        return RTCIceServer(
            urls=["stun:example2.com", "turn:example2.com"],
            username="user",
            credential="pass",
        )

    register_ice_server(hass, get_ice_server)

    await client.send_json_auto_id(
        {"type": "camera/webrtc/get_client_config", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "configuration": {
            "iceServers": [
                {"urls": "stun:stun.home-assistant.io:3478"},
                {
                    "urls": ["stun:example2.com", "turn:example2.com"],
                    "username": "user",
                    "credential": "pass",
                },
            ],
        },
        "getCandidatesUpfront": False,
    }


@pytest.mark.usefixtures("mock_camera_hls")
async def test_ws_get_client_config_no_rtc_camera(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get WebRTC client config."""
    await async_setup_component(hass, "camera", {})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "camera/webrtc/get_client_config", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"] == {
        "code": "webrtc_get_client_config_failed",
        "message": "Camera does not support WebRTC, frontend_stream_type=hls",
    }


async def provide_webrtc_answer(stream_source: str, offer: str, stream_id: str) -> str:
    """Simulate an rtsp to webrtc provider."""
    assert stream_source == STREAM_SOURCE
    assert offer == WEBRTC_OFFER
    return WEBRTC_ANSWER


@pytest.fixture(name="mock_rtsp_to_webrtc")
def mock_rtsp_to_webrtc_fixture(hass: HomeAssistant) -> Generator[Mock]:
    """Fixture that registers a mock rtsp to webrtc provider."""
    mock_provider = Mock(side_effect=provide_webrtc_answer)
    unsub = async_register_rtsp_to_web_rtc_provider(hass, "mock_domain", mock_provider)
    yield mock_provider
    unsub()


@pytest.mark.usefixtures("mock_camera_webrtc")
async def test_websocket_webrtc_offer(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test initiating a WebRTC stream with offer and answer."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session_id"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": WEBRTC_ANSWER,
    }


@pytest.mark.usefixtures("mock_camera_webrtc")
async def test_websocket_webrtc_offer_invalid_entity(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC with a camera entity that does not exist."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.does_not_exist",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": "Camera not found",
    }


@pytest.mark.usefixtures("mock_camera_webrtc")
async def test_websocket_webrtc_offer_missing_offer(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC stream with missing required fields."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
        }
    )
    response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.usefixtures("mock_camera_webrtc_frontendtype_only")
async def test_websocket_webrtc_offer_failure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC stream that fails handling the offer."""
    client = await hass_ws_client(hass)

    camera_obj = get_camera_from_entity_id(hass, "camera.demo_camera")
    camera_obj._webrtc_sync_offer = True  # Setting it to True to simulate async_handle_web_rtc_offer would be overwritten

    with patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        side_effect=HomeAssistantError("offer failed"),
    ):
        await client.send_json_auto_id(
            {
                "type": "camera/webrtc/offer",
                "entity_id": "camera.demo_camera",
                "offer": WEBRTC_OFFER,
            }
        )
        response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session_id"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "offer failed",
    }


@pytest.mark.usefixtures("mock_camera_webrtc_frontendtype_only")
async def test_websocket_webrtc_offer_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC stream with timeout handling the offer."""
    client = await hass_ws_client(hass)

    camera_obj = get_camera_from_entity_id(hass, "camera.demo_camera")
    camera_obj._webrtc_sync_offer = True  # Setting it to True to simulate async_handle_web_rtc_offer would be overwritten

    with patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        side_effect=TimeoutError(),
    ):
        await client.send_json_auto_id(
            {
                "type": "camera/webrtc/offer",
                "entity_id": "camera.demo_camera",
                "offer": WEBRTC_OFFER,
            }
        )
        response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session_id"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "Timeout handling WebRTC offer",
    }


@pytest.mark.usefixtures("mock_camera")
async def test_websocket_webrtc_offer_invalid_stream_type(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC initiating for a camera with a different stream_type."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"] == {
        "code": "webrtc_offer_failed",
        "message": "Camera does not support WebRTC, frontend_stream_type=hls",
    }


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_rtsp_to_webrtc_offer(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_rtsp_to_webrtc: Mock,
) -> None:
    """Test creating a webrtc offer from an rstp provider."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session_id"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": WEBRTC_ANSWER,
    }

    assert mock_rtsp_to_webrtc.called


@pytest.fixture(name="mock_hls_stream_source")
async def mock_hls_stream_source_fixture() -> Generator[AsyncMock]:
    """Fixture to create an HLS stream source."""
    with patch(
        "homeassistant.components.camera.Camera.stream_source",
        return_value=HLS_STREAM_SOURCE,
    ) as mock_hls_stream_source:
        yield mock_hls_stream_source


@pytest.mark.usefixtures(
    "mock_camera",
    "mock_hls_stream_source",  # Not an RTSP stream source
    "mock_camera_webrtc_frontendtype_only",
)
async def test_unsupported_rtsp_to_webrtc_stream_type(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test rtsp-to-webrtc is not registered for non-RTSP streams."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session_id"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "Camera does not support WebRTC",
    }


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_rtsp_to_webrtc_provider_unregistered(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test creating a webrtc offer from an rstp provider."""
    mock_provider = Mock(side_effect=provide_webrtc_answer)
    unsub = async_register_rtsp_to_web_rtc_provider(hass, "mock_domain", mock_provider)

    client = await hass_ws_client(hass)

    # Registered provider can handle the WebRTC offer
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session_id"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": WEBRTC_ANSWER,
    }

    assert mock_provider.called
    mock_provider.reset_mock()

    # Unregister provider, then verify the WebRTC offer cannot be handled
    unsub()
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response.get("type") == TYPE_RESULT
    assert not response["success"]
    assert response["error"] == {
        "code": "webrtc_offer_failed",
        "message": "Camera does not support WebRTC, frontend_stream_type=hls",
    }

    assert not mock_provider.called


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_rtsp_to_webrtc_offer_not_accepted(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a provider that can't satisfy the rtsp to webrtc offer."""

    async def provide_none(
        stream_source: str, offer: str, stream_id: str
    ) -> str | None:
        """Simulate a provider that can't accept the offer."""
        return None

    mock_provider = Mock(side_effect=provide_none)
    unsub = async_register_rtsp_to_web_rtc_provider(hass, "mock_domain", mock_provider)
    client = await hass_ws_client(hass)

    # Registered provider can handle the WebRTC offer
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.demo_camera",
            "offer": WEBRTC_OFFER,
        }
    )
    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    subscription_id = response["id"]

    # Session id
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"]["type"] == "session_id"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "error",
        "code": "webrtc_offer_failed",
        "message": "Camera does not support WebRTC",
    }

    assert mock_provider.called

    unsub()
