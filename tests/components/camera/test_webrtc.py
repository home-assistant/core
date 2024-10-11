"""Test camera WebRTC."""

import pytest

from homeassistant.components.camera import Camera
from homeassistant.components.camera.const import StreamType
from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.components.camera.webrtc import (
    DATA_ICE_SERVERS,
    CameraWebRTCProvider,
    RTCIceServer,
    async_register_webrtc_provider,
    register_ice_server,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


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

        async def async_is_supported(self, stream_source: str) -> bool:
            """Determine if the provider supports the stream source."""
            nonlocal stream_supported
            return stream_supported

        async def async_handle_web_rtc_offer(
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

        async def async_is_supported(self, stream_source: str) -> bool:
            """Determine if the provider supports the stream source."""
            return True

        async def async_handle_web_rtc_offer(
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

        async def async_is_supported(self, stream_source: str) -> bool:
            """Determine if the provider supports the stream source."""
            return True

        async def async_handle_web_rtc_offer(
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


@pytest.mark.usefixtures("mock_camera_web_rtc")
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
        "configuration": {"iceServers": [{"urls": "stun:stun.home-assistant.io:3478"}]}
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
        "code": "web_rtc_offer_failed",
        "message": "Camera does not support WebRTC, frontend_stream_type=hls",
    }
