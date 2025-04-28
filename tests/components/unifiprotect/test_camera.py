"""Test the UniFi Protect camera platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import Camera as ProtectCamera, CameraChannel, StateType
from uiprotect.exceptions import NvrError
from uiprotect.websocket import WebsocketState
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    CameraEntityFeature,
    CameraState,
    CameraWebRTCProvider,
    StreamType,
    WebRTCSendMessage,
    async_get_image,
    async_get_stream_source,
    async_register_webrtc_provider,
)
from homeassistant.components.unifiprotect.const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DEFAULT_ATTRIBUTION,
    DOMAIN,
)
from homeassistant.components.unifiprotect.utils import get_camera_base_name
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .utils import (
    Camera,
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    init_entry,
    remove_entities,
    time_changed,
)


class MockWebRTCProvider(CameraWebRTCProvider):
    """WebRTC provider."""

    @property
    def domain(self) -> str:
        """Return the integration domain of the provider."""
        return DOMAIN

    @callback
    def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return True

    async def async_handle_async_webrtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle the WebRTC offer and return the answer via the provided callback."""

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle the WebRTC candidate."""

    @callback
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""


@pytest.fixture
async def web_rtc_provider(hass: HomeAssistant) -> None:
    """Fixture to enable WebRTC provider for camera entities."""
    await async_setup_component(hass, "camera", {})
    async_register_webrtc_provider(hass, MockWebRTCProvider())


def validate_default_camera_entity(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
) -> str:
    """Validate a camera entity."""

    channel = camera_obj.channels[channel_id]

    camera_name = get_camera_base_name(channel)
    entity_name = f"{camera_obj.name} {camera_name}"
    unique_id = f"{camera_obj.mac}_{channel.id}"
    entity_id = f"camera.{entity_name.replace(' ', '_').lower()}"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is False
    assert entity.unique_id == unique_id

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entity.device_id)
    assert device
    assert device.manufacturer == "Ubiquiti"
    assert device.name == camera_obj.name
    assert device.model == camera_obj.market_name or camera_obj.type
    assert device.model_id == camera_obj.type

    return entity_id


def validate_rtsps_camera_entity(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
) -> str:
    """Validate a disabled RTSPS camera entity."""

    channel = camera_obj.channels[channel_id]

    entity_name = f"{camera_obj.name} {channel.name} Resolution Channel"
    unique_id = f"{camera_obj.mac}_{channel.id}"
    entity_id = f"camera.{entity_name.replace(' ', '_').lower()}"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    return entity_id


def validate_rtsp_camera_entity(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
) -> str:
    """Validate a disabled RTSP camera entity."""

    channel = camera_obj.channels[channel_id]

    entity_name = f"{camera_obj.name} {channel.name} Resolution Channel (Insecure)"
    unique_id = f"{camera_obj.mac}_{channel.id}_insecure"
    entity_id = f"camera.{entity_name.replace(' ', '_').replace('(', '').replace(')', '').lower()}"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    return entity_id


def validate_common_camera_state(
    hass: HomeAssistant,
    channel: CameraChannel,
    entity_id: str,
    features: int = CameraEntityFeature.STREAM,
):
    """Validate state that is common to all camera entity, regardless of type."""
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert entity_state.attributes[ATTR_SUPPORTED_FEATURES] == features
    assert entity_state.attributes[ATTR_WIDTH] == channel.width
    assert entity_state.attributes[ATTR_HEIGHT] == channel.height
    assert entity_state.attributes[ATTR_FPS] == channel.fps
    assert entity_state.attributes[ATTR_BITRATE] == channel.bitrate
    assert entity_state.attributes[ATTR_CHANNEL_ID] == channel.id


async def validate_rtsps_camera_state(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
    entity_id: str,
    features: int = CameraEntityFeature.STREAM,
):
    """Validate a camera's state."""
    channel = camera_obj.channels[channel_id]

    assert await async_get_stream_source(hass, entity_id) == channel.rtsps_no_srtp_url
    validate_common_camera_state(hass, channel, entity_id, features)


async def validate_rtsp_camera_state(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
    entity_id: str,
    features: int = CameraEntityFeature.STREAM,
):
    """Validate a camera's state."""
    channel = camera_obj.channels[channel_id]

    assert await async_get_stream_source(hass, entity_id) == channel.rtsp_url
    validate_common_camera_state(hass, channel, entity_id, features)


async def validate_no_stream_camera_state(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
    entity_id: str,
    features: int = CameraEntityFeature.STREAM,
):
    """Validate a camera's state."""
    channel = camera_obj.channels[channel_id]

    assert await async_get_stream_source(hass, entity_id) is None
    validate_common_camera_state(hass, channel, entity_id, features)


async def test_basic_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera_all: ProtectCamera,
    doorbell: ProtectCamera,
) -> None:
    """Test working setup of unifiprotect entry."""

    camera_high_only = camera_all.model_copy()
    camera_high_only.channels = [c.model_copy() for c in camera_all.channels]
    camera_high_only.name = "Test Camera 1"
    camera_high_only.channels[0].is_rtsp_enabled = True
    camera_high_only.channels[1].is_rtsp_enabled = False
    camera_high_only.channels[2].is_rtsp_enabled = False

    camera_medium_only = camera_all.model_copy()
    camera_medium_only.channels = [c.model_copy() for c in camera_all.channels]
    camera_medium_only.name = "Test Camera 2"
    camera_medium_only.channels[0].is_rtsp_enabled = False
    camera_medium_only.channels[1].is_rtsp_enabled = True
    camera_medium_only.channels[2].is_rtsp_enabled = False

    camera_all.name = "Test Camera 3"

    camera_no_channels = camera_all.model_copy()
    camera_no_channels.channels = [c.model_copy() for c in camera_all.channels]
    camera_no_channels.name = "Test Camera 4"
    camera_no_channels.channels[0].is_rtsp_enabled = False
    camera_no_channels.channels[1].is_rtsp_enabled = False
    camera_no_channels.channels[2].is_rtsp_enabled = False

    doorbell.name = "Test Camera 5"

    devices = [
        camera_high_only,
        camera_medium_only,
        camera_all,
        camera_no_channels,
        doorbell,
    ]
    await init_entry(hass, ufp, devices)

    assert_entity_counts(hass, Platform.CAMERA, 14, 6)

    # test camera 1
    entity_id = validate_default_camera_entity(hass, camera_high_only, 0)
    await validate_rtsps_camera_state(hass, camera_high_only, 0, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_high_only, 0)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_high_only, 0, entity_id)

    # test camera 2
    entity_id = validate_default_camera_entity(hass, camera_medium_only, 1)
    await validate_rtsps_camera_state(hass, camera_medium_only, 1, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_medium_only, 1)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_medium_only, 1, entity_id)

    # test camera 3
    entity_id = validate_default_camera_entity(hass, camera_all, 0)
    await validate_rtsps_camera_state(hass, camera_all, 0, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_all, 0)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_all, 0, entity_id)

    entity_id = validate_rtsps_camera_entity(hass, camera_all, 1)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsps_camera_state(hass, camera_all, 1, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_all, 1)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_all, 1, entity_id)

    entity_id = validate_rtsps_camera_entity(hass, camera_all, 2)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsps_camera_state(hass, camera_all, 2, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_all, 2)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_all, 2, entity_id)

    # test camera 4
    entity_id = validate_default_camera_entity(hass, camera_no_channels, 0)
    await validate_no_stream_camera_state(
        hass, camera_no_channels, 0, entity_id, features=0
    )

    # test camera 5
    entity_id = validate_default_camera_entity(hass, doorbell, 0)
    await validate_rtsps_camera_state(hass, doorbell, 0, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, doorbell, 0)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, doorbell, 0, entity_id)

    entity_id = validate_default_camera_entity(hass, doorbell, 3)
    await validate_no_stream_camera_state(hass, doorbell, 3, entity_id, features=0)


@pytest.mark.usefixtures("web_rtc_provider")
async def test_webrtc_support(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera_all: ProtectCamera,
) -> None:
    """Test webrtc support is available."""
    camera_high_only = camera_all.model_copy()
    camera_high_only.channels = [c.model_copy() for c in camera_all.channels]
    camera_high_only.name = "Test Camera 1"
    camera_high_only.channels[0].is_rtsp_enabled = True
    camera_high_only.channels[1].is_rtsp_enabled = False
    camera_high_only.channels[2].is_rtsp_enabled = False
    await init_entry(hass, ufp, [camera_high_only])
    entity_id = validate_default_camera_entity(hass, camera_high_only, 0)
    state = hass.states.get(entity_id)
    assert state
    assert StreamType.WEB_RTC in state.attributes["frontend_stream_type"]


async def test_adopt(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Test setting up camera with no camera channels."""

    camera1 = camera.model_copy()
    camera1.channels = []

    await init_entry(hass, ufp, [camera1])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)

    await remove_entities(hass, ufp, [camera1])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)
    camera1.channels = []
    await adopt_devices(hass, ufp, [camera1])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)

    camera1.channels = camera.channels
    for channel in camera1.channels:
        channel._api = ufp.api

    mock_msg = Mock()
    mock_msg.changed_data = {"channels": camera.channels}
    mock_msg.new_obj = camera1
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)

    await remove_entities(hass, ufp, [camera1])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)
    await adopt_devices(hass, ufp, [camera1])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)


async def test_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Test retrieving camera image."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)

    ufp.api.get_camera_snapshot = AsyncMock()

    await async_get_image(hass, "camera.test_camera_high_resolution_channel")
    ufp.api.get_camera_snapshot.assert_called_once()


async def test_package_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: ProtectCamera
) -> None:
    """Test retrieving package camera image."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.CAMERA, 3, 2)

    ufp.api.get_package_camera_snapshot = AsyncMock()

    await async_get_image(hass, "camera.test_camera_package_camera")
    ufp.api.get_package_camera_snapshot.assert_called_once()


async def test_camera_generic_update(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Tests generic entity update service."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    assert await async_setup_component(hass, "homeassistant", {})

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"

    ufp.api.update = AsyncMock(return_value=None)
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"


async def test_camera_interval_update(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Interval updates updates camera entity."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"

    new_camera = camera.model_copy()
    new_camera.is_recording = True

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.update = AsyncMock(return_value=ufp.api.bootstrap)
    await time_changed(hass, DEVICE_UPDATE_INTERVAL)

    state = hass.states.get(entity_id)
    assert state and state.state == "recording"


async def test_camera_bad_interval_update(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Interval updates marks camera unavailable."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"

    # update fails
    ufp.api.update = AsyncMock(side_effect=NvrError)
    await time_changed(hass, DEVICE_UPDATE_INTERVAL)

    state = hass.states.get(entity_id)
    assert state and state.state == "unavailable"

    # next update succeeds
    ufp.api.update = AsyncMock(return_value=ufp.api.bootstrap)
    await time_changed(hass, DEVICE_UPDATE_INTERVAL)

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"


async def test_camera_websocket_disconnected(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Test the websocket gets disconnected and reconnected."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    state = hass.states.get(entity_id)
    assert state and state.state == CameraState.IDLE

    # websocket disconnects
    ufp.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state and state.state == STATE_UNAVAILABLE

    # websocket reconnects
    ufp.ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state and state.state == CameraState.IDLE


async def test_camera_ws_update(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """WS update updates camera entity."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"

    new_camera = camera.model_copy()
    new_camera.is_recording = True

    no_camera = camera.model_copy()
    no_camera.is_adopted = False

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera
    ufp.ws_msg(mock_msg)

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = no_camera
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state and state.state == "recording"


async def test_camera_ws_update_offline(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """WS updates marks camera unavailable."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"

    # camera goes offline
    new_camera = camera.model_copy()
    new_camera.state = StateType.DISCONNECTED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state and state.state == "unavailable"

    # camera comes back online
    new_camera.state = StateType.CONNECTED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"


async def test_camera_enable_motion(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Tests generic entity update service."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    camera.__pydantic_fields__["set_motion_detection"] = Mock(final=False, frozen=False)
    camera.set_motion_detection = AsyncMock()

    await hass.services.async_call(
        "camera",
        "enable_motion_detection",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    camera.set_motion_detection.assert_called_once_with(True)


async def test_camera_disable_motion(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Tests generic entity update service."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    camera.__pydantic_fields__["set_motion_detection"] = Mock(final=False, frozen=False)
    camera.set_motion_detection = AsyncMock()

    await hass.services.async_call(
        "camera",
        "disable_motion_detection",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    camera.set_motion_detection.assert_called_once_with(False)
