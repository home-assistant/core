"""Test camera WebRTC."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from webrtc_models import RTCIceCandidate, RTCIceCandidateInit, RTCIceServer

from homeassistant.components.camera import (
    DATA_ICE_SERVERS,
    Camera,
    CameraWebRTCProvider,
    StreamType,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCError,
    WebRTCMessage,
    WebRTCSendMessage,
    async_register_ice_servers,
    async_register_webrtc_provider,
    get_camera_from_entity_id,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant, callback
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from .common import STREAM_SOURCE, WEBRTC_ANSWER, SomeTestProvider

from tests.typing import WebSocketGenerator

WEBRTC_OFFER = "v=0\r\n"
HLS_STREAM_SOURCE = "http://127.0.0.1/example.m3u"
TEST_INTEGRATION_DOMAIN = "test"


class Go2RTCProvider(SomeTestProvider):
    """go2rtc provider."""

    @property
    def domain(self) -> str:
        """Return the integration domain of the provider."""
        return "go2rtc"


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_async_register_webrtc_provider(
    hass: HomeAssistant,
) -> None:
    """Test registering a WebRTC provider."""
    camera = get_camera_from_entity_id(hass, "camera.demo_camera")
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.HLS}

    provider = SomeTestProvider()
    unregister = async_register_webrtc_provider(hass, provider)
    await hass.async_block_till_done()

    assert camera.camera_capabilities.frontend_stream_types == {
        StreamType.HLS,
        StreamType.WEB_RTC,
    }

    # Mark stream as unsupported
    provider._is_supported = False
    # Manually refresh the provider
    await camera.async_refresh_providers()

    assert camera.camera_capabilities.frontend_stream_types == {StreamType.HLS}

    # Mark stream as supported
    provider._is_supported = True
    # Manually refresh the provider
    await camera.async_refresh_providers()
    assert camera.camera_capabilities.frontend_stream_types == {
        StreamType.HLS,
        StreamType.WEB_RTC,
    }

    unregister()
    await hass.async_block_till_done()

    assert camera.camera_capabilities.frontend_stream_types == {StreamType.HLS}


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_async_register_webrtc_provider_twice(
    hass: HomeAssistant,
    register_test_provider: SomeTestProvider,
) -> None:
    """Test registering a WebRTC provider twice should raise."""
    with pytest.raises(ValueError, match="Provider already registered"):
        async_register_webrtc_provider(hass, register_test_provider)


async def test_async_register_webrtc_provider_camera_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test registering a WebRTC provider when camera is not loaded."""
    with pytest.raises(ValueError, match="Unexpected state, camera not loaded"):
        async_register_webrtc_provider(hass, SomeTestProvider())


@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_async_register_ice_server(
    hass: HomeAssistant,
) -> None:
    """Test registering an ICE server."""
    # Clear any existing ICE servers
    hass.data[DATA_ICE_SERVERS].clear()

    called = 0

    @callback
    def get_ice_servers() -> list[RTCIceServer]:
        nonlocal called
        called += 1
        return [
            RTCIceServer(urls="stun:example.com"),
            RTCIceServer(urls="turn:example.com"),
        ]

    unregister = async_register_ice_servers(hass, get_ice_servers)
    assert not called

    camera = get_camera_from_entity_id(hass, "camera.async")
    config = camera.async_get_webrtc_client_configuration()

    assert config.configuration.ice_servers == [
        RTCIceServer(urls="stun:example.com"),
        RTCIceServer(urls="turn:example.com"),
    ]
    assert called == 1

    # register another ICE server
    called_2 = 0

    @callback
    def get_ice_servers_2() -> list[RTCIceServer]:
        nonlocal called_2
        called_2 += 1
        return [
            RTCIceServer(
                urls=["stun:example2.com", "turn:example2.com"],
                username="user",
                credential="pass",
            )
        ]

    unregister_2 = async_register_ice_servers(hass, get_ice_servers_2)

    config = camera.async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == [
        RTCIceServer(urls="stun:example.com"),
        RTCIceServer(urls="turn:example.com"),
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

    config = camera.async_get_webrtc_client_configuration()
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

    config = camera.async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == []


@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_ws_get_client_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get WebRTC client config."""
    await async_setup_component(hass, "camera", {})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "camera/webrtc/get_client_config", "entity_id": "camera.async"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "configuration": {
            "iceServers": [
                {
                    "urls": [
                        "stun:stun.home-assistant.io:80",
                        "stun:stun.home-assistant.io:3478",
                    ]
                },
            ],
        },
    }

    @callback
    def get_ice_server() -> list[RTCIceServer]:
        return [
            RTCIceServer(
                urls=["stun:example2.com", "turn:example2.com"],
                username="user",
                credential="pass",
            )
        ]

    async_register_ice_servers(hass, get_ice_server)

    await client.send_json_auto_id(
        {"type": "camera/webrtc/get_client_config", "entity_id": "camera.async"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "configuration": {
            "iceServers": [
                {
                    "urls": [
                        "stun:stun.home-assistant.io:80",
                        "stun:stun.home-assistant.io:3478",
                    ]
                },
                {
                    "urls": ["stun:example2.com", "turn:example2.com"],
                    "username": "user",
                    "credential": "pass",
                },
            ],
        },
    }


@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_ws_get_client_config_custom_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get WebRTC client config."""
    await async_process_ha_core_config(
        hass,
        {"webrtc": {"ice_servers": [{"url": "stun:custom_stun_server:3478"}]}},
    )

    await async_setup_component(hass, "camera", {})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "camera/webrtc/get_client_config", "entity_id": "camera.async"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "configuration": {"iceServers": [{"urls": ["stun:custom_stun_server:3478"]}]},
    }


@pytest.mark.usefixtures("mock_camera")
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
        "message": "Camera does not support WebRTC, frontend_stream_types={<StreamType.HLS: 'hls'>}",
    }


async def provide_webrtc_answer(stream_source: str, offer: str, stream_id: str) -> str:
    """Simulate an rtsp to webrtc provider."""
    assert stream_source == STREAM_SOURCE
    assert offer == WEBRTC_OFFER
    return WEBRTC_ANSWER


@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_websocket_webrtc_offer(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test initiating a WebRTC stream with offer and answer."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.async",
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
    assert response["event"]["type"] == "session"

    # Answer
    response = await client.receive_json()
    assert response["id"] == subscription_id
    assert response["type"] == "event"
    assert response["event"] == {
        "type": "answer",
        "answer": WEBRTC_ANSWER,
    }

    # Unsubscribe/Close session
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]


@pytest.mark.filterwarnings(
    "ignore:Using RTCIceCandidate is deprecated. Use RTCIceCandidateInit instead"
)
@pytest.mark.usefixtures("mock_stream_source", "mock_camera")
async def test_websocket_webrtc_offer_webrtc_provider_deprecated(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    register_test_provider: SomeTestProvider,
) -> None:
    """Test initiating a WebRTC stream with a webrtc provider with the deprecated class."""
    await _test_websocket_webrtc_offer_webrtc_provider(
        hass,
        hass_ws_client,
        register_test_provider,
        WebRTCCandidate(RTCIceCandidate("candidate")),
        {"type": "candidate", "candidate": {"candidate": "candidate"}},
    )


@pytest.mark.parametrize(
    ("message", "expected_frontend_message"),
    [
        (
            WebRTCCandidate(RTCIceCandidateInit("candidate")),
            {
                "type": "candidate",
                "candidate": {"candidate": "candidate", "sdpMLineIndex": 0},
            },
        ),
        (
            WebRTCError("webrtc_offer_failed", "error"),
            {"type": "error", "code": "webrtc_offer_failed", "message": "error"},
        ),
        (WebRTCAnswer("answer"), {"type": "answer", "answer": "answer"}),
    ],
    ids=["candidate", "error", "answer"],
)
@pytest.mark.usefixtures("mock_stream_source", "mock_camera")
async def test_websocket_webrtc_offer_webrtc_provider(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    register_test_provider: SomeTestProvider,
    message: WebRTCMessage,
    expected_frontend_message: dict[str, Any],
) -> None:
    """Test initiating a WebRTC stream with a webrtc provider."""
    await _test_websocket_webrtc_offer_webrtc_provider(
        hass,
        hass_ws_client,
        register_test_provider,
        message,
        expected_frontend_message,
    )


async def _test_websocket_webrtc_offer_webrtc_provider(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    register_test_provider: SomeTestProvider,
    message: WebRTCMessage,
    expected_frontend_message: dict[str, Any],
) -> None:
    """Test initiating a WebRTC stream with a webrtc provider."""
    client = await hass_ws_client(hass)
    with (
        patch.object(
            register_test_provider, "async_handle_async_webrtc_offer", autospec=True
        ) as mock_async_handle_async_webrtc_offer,
        patch.object(
            register_test_provider, "async_close_session", autospec=True
        ) as mock_async_close_session,
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
        mock_async_handle_async_webrtc_offer.assert_called_once()
        assert mock_async_handle_async_webrtc_offer.call_args[0][1] == WEBRTC_OFFER
        send_message: WebRTCSendMessage = (
            mock_async_handle_async_webrtc_offer.call_args[0][3]
        )

        # Session id
        response = await client.receive_json()
        assert response["id"] == subscription_id
        assert response["type"] == "event"
        assert response["event"]["type"] == "session"
        session_id = response["event"]["session_id"]

        send_message(message)

        response = await client.receive_json()
        assert response["id"] == subscription_id
        assert response["type"] == "event"
        assert response["event"] == expected_frontend_message

        # Unsubscribe/Close session
        await client.send_json_auto_id(
            {
                "type": "unsubscribe_events",
                "subscription": subscription_id,
            }
        )
        msg = await client.receive_json()
        assert msg["success"]
        mock_async_close_session.assert_called_once_with(session_id)


async def test_websocket_webrtc_offer_invalid_entity(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test WebRTC with a camera entity that does not exist."""
    await async_setup_component(hass, "camera", {})
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


@pytest.mark.usefixtures("mock_test_webrtc_cameras")
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
        "message": "Camera does not support WebRTC, frontend_stream_types={<StreamType.HLS: 'hls'>}",
    }


@pytest.fixture(name="mock_hls_stream_source")
async def mock_hls_stream_source_fixture() -> AsyncGenerator[AsyncMock]:
    """Fixture to create an HLS stream source."""
    with patch(
        "homeassistant.components.camera.Camera.stream_source",
        return_value=HLS_STREAM_SOURCE,
    ) as mock_hls_stream_source:
        yield mock_hls_stream_source


@pytest.mark.parametrize(
    ("frontend_candidate", "expected_candidate"),
    [
        (
            {"candidate": "candidate", "sdpMLineIndex": 0},
            RTCIceCandidateInit("candidate"),
        ),
        (
            {"candidate": "candidate", "sdpMLineIndex": 1},
            RTCIceCandidateInit("candidate", sdp_m_line_index=1),
        ),
        (
            {"candidate": "candidate", "sdpMid": "1"},
            RTCIceCandidateInit("candidate", sdp_mid="1"),
        ),
    ],
    ids=["candidate", "candidate-mline-index", "candidate-mid"],
)
@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_ws_webrtc_candidate(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    frontend_candidate: dict[str, Any],
    expected_candidate: RTCIceCandidateInit,
) -> None:
    """Test ws webrtc candidate command."""
    client = await hass_ws_client(hass)
    session_id = "session_id"
    with patch.object(
        get_camera_from_entity_id(hass, "camera.async"), "async_on_webrtc_candidate"
    ) as mock_on_webrtc_candidate:
        await client.send_json_auto_id(
            {
                "type": "camera/webrtc/candidate",
                "entity_id": "camera.async",
                "session_id": session_id,
                "candidate": frontend_candidate,
            }
        )
        response = await client.receive_json()
        assert response["type"] == TYPE_RESULT
        assert response["success"]
        mock_on_webrtc_candidate.assert_called_once_with(session_id, expected_candidate)


@pytest.mark.parametrize(
    ("message", "expected_error_msg"),
    [
        (
            {"sdpMLineIndex": 0},
            (
                'Field "candidate" of type str is missing in RTCIceCandidateInit instance'
                " for dictionary value @ data['candidate']. Got {'sdpMLineIndex': 0}"
            ),
        ),
        (
            {"candidate": "candidate", "sdpMLineIndex": -1},
            (
                "sdpMLineIndex must be greater than or equal to 0 for dictionary value @ "
                "data['candidate']. Got {'candidate': 'candidate', 'sdpMLineIndex': -1}"
            ),
        ),
    ],
    ids=[
        "candidate missing",
        "spd_mline_index smaller than 0",
    ],
)
@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_ws_webrtc_candidate_invalid_candidate_message(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    message: dict,
    expected_error_msg: str,
) -> None:
    """Test ws WebRTC candidate command for a camera with a different stream_type."""
    client = await hass_ws_client(hass)
    with patch("homeassistant.components.camera.Camera.async_on_webrtc_candidate"):
        await client.send_json_auto_id(
            {
                "type": "camera/webrtc/candidate",
                "entity_id": "camera.async",
                "session_id": "session_id",
                "candidate": message,
            }
        )
        response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"] == {
        "code": "invalid_format",
        "message": expected_error_msg,
    }


@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_ws_webrtc_candidate_not_supported(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test ws webrtc candidate command is raising if not supported."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": "camera.async_no_candidate",
            "session_id": "session_id",
            "candidate": {"candidate": "candidate"},
        }
    )
    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": "Cannot handle WebRTC candidate",
    }


@pytest.mark.usefixtures("mock_camera", "mock_stream_source")
async def test_ws_webrtc_candidate_webrtc_provider(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    register_test_provider: SomeTestProvider,
) -> None:
    """Test ws webrtc candidate command with WebRTC provider."""
    with patch.object(
        register_test_provider, "async_on_webrtc_candidate"
    ) as mock_on_webrtc_candidate:
        client = await hass_ws_client(hass)
        session_id = "session_id"
        candidate = "candidate"
        await client.send_json_auto_id(
            {
                "type": "camera/webrtc/candidate",
                "entity_id": "camera.demo_camera",
                "session_id": session_id,
                "candidate": {"candidate": candidate, "sdpMLineIndex": 1},
            }
        )
        response = await client.receive_json()
        assert response["type"] == TYPE_RESULT
        assert response["success"]
        mock_on_webrtc_candidate.assert_called_once_with(
            session_id, RTCIceCandidateInit(candidate, sdp_m_line_index=1)
        )


async def test_ws_webrtc_candidate_invalid_entity(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test ws WebRTC candidate command with a camera entity that does not exist."""
    await async_setup_component(hass, "camera", {})
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": "camera.does_not_exist",
            "session_id": "session_id",
            "candidate": {"candidate": "candidate"},
        }
    )
    response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": "Camera not found",
    }


@pytest.mark.usefixtures("mock_test_webrtc_cameras")
async def test_ws_webrtc_canidate_missing_candidate(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test ws WebRTC candidate command with missing required fields."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": "camera.async",
            "session_id": "session_id",
        }
    )
    response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.usefixtures("mock_camera")
async def test_ws_webrtc_candidate_invalid_stream_type(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test ws WebRTC candidate command for a camera with a different stream_type."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": "camera.demo_camera",
            "session_id": "session_id",
            "candidate": {"candidate": "candidate"},
        }
    )
    response = await client.receive_json()

    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"] == {
        "code": "webrtc_candidate_failed",
        "message": "Camera does not support WebRTC, frontend_stream_types={<StreamType.HLS: 'hls'>}",
    }


async def test_webrtc_provider_optional_interface(hass: HomeAssistant) -> None:
    """Test optional interface for WebRTC provider."""

    class OnlyRequiredInterfaceProvider(CameraWebRTCProvider):
        """Test provider."""

        @property
        def domain(self) -> str:
            """Return the domain of the provider."""
            return "test"

        @callback
        def async_is_supported(self, stream_source: str) -> bool:
            """Determine if the provider supports the stream source."""
            return True

        async def async_handle_async_webrtc_offer(
            self,
            camera: Camera,
            offer_sdp: str,
            session_id: str,
            send_message: WebRTCSendMessage,
        ) -> None:
            """Handle the WebRTC offer and return the answer via the provided callback.

            Return value determines if the offer was handled successfully.
            """
            send_message(WebRTCAnswer(answer="answer"))

        async def async_on_webrtc_candidate(
            self, session_id: str, candidate: RTCIceCandidateInit
        ) -> None:
            """Handle the WebRTC candidate."""

    provider = OnlyRequiredInterfaceProvider()
    # Call all interface methods
    assert provider.async_is_supported("stream_source") is True
    await provider.async_handle_async_webrtc_offer(
        Mock(), "offer_sdp", "session_id", Mock()
    )
    await provider.async_on_webrtc_candidate(
        "session_id", RTCIceCandidateInit("candidate")
    )
    provider.async_close_session("session_id")
