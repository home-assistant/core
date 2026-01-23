"""Test the UniFi Protect camera platform."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import Camera as ProtectCamera, CameraChannel, Light, StateType
from uiprotect.exceptions import ClientError, NotAuthorized, NvrError
from uiprotect.websocket import WebsocketState
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    CameraCapabilities,
    CameraEntityFeature,
    CameraState,
    CameraWebRTCProvider,
    StreamType,
    WebRTCSendMessage,
    async_get_image,
    async_get_stream_source,
    async_register_webrtc_provider,
    get_camera_from_entity_id,
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
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from . import patch_ufp_method
from .conftest import create_mock_rtsps_streams
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

    camera_name = get_camera_base_name(channel)
    entity_name = f"{camera_obj.name} {camera_name}"
    unique_id = f"{camera_obj.mac}_{channel.id}"
    entity_id = f"camera.{entity_name.replace(' ', '_').lower()}"

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

    # Stream source comes from public API - check that it has a valid RTSPS URL
    stream_source = await async_get_stream_source(hass, entity_id)
    assert stream_source is not None
    assert stream_source.startswith("rtsps://")
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

    # All cameras get entities for all channels regardless of is_rtsp_enabled
    # Stream availability is determined by the public API, not is_rtsp_enabled

    camera1 = camera_all.model_copy()
    camera1.channels = [c.model_copy() for c in camera_all.channels]
    camera1.name = "Test Camera 1"

    camera2 = camera_all.model_copy()
    camera2.channels = [c.model_copy() for c in camera_all.channels]
    camera2.name = "Test Camera 2"

    camera_all.name = "Test Camera 3"

    # Doorbell with package camera
    doorbell.name = "Test Camera 5"
    doorbell.feature_flags.has_package_camera = True

    devices = [
        camera1,
        camera2,
        camera_all,
        doorbell,
    ]
    await init_entry(hass, ufp, devices)

    # All cameras get all channels as entities:
    # camera1: 3 entities (high enabled, medium disabled, low disabled)
    # camera2: 3 entities (high enabled, medium disabled, low disabled)
    # camera_all: 3 entities (high enabled, medium disabled, low disabled)
    # doorbell: 4 entities (high enabled, medium disabled, low disabled, package disabled)
    # Total: 13 entities, 4 enabled by default (one "high" per camera)
    assert_entity_counts(hass, Platform.CAMERA, 13, 4)

    # test camera 1 - high channel should be enabled
    entity_id = validate_default_camera_entity(hass, camera1, 0)
    await validate_rtsps_camera_state(hass, camera1, 0, entity_id)

    # verify medium and low channels exist but are disabled
    validate_rtsps_camera_entity(hass, camera1, 1)
    validate_rtsps_camera_entity(hass, camera1, 2)

    # test camera 3
    entity_id = validate_default_camera_entity(hass, camera_all, 0)
    await validate_rtsps_camera_state(hass, camera_all, 0, entity_id)

    # enable medium channel and verify
    entity_id = validate_rtsps_camera_entity(hass, camera_all, 1)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsps_camera_state(hass, camera_all, 1, entity_id)

    # enable low channel and verify
    entity_id = validate_rtsps_camera_entity(hass, camera_all, 2)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)
    await validate_rtsps_camera_state(hass, camera_all, 2, entity_id)

    # test doorbell - high channel should be enabled
    entity_id = validate_default_camera_entity(hass, doorbell, 0)
    await validate_rtsps_camera_state(hass, doorbell, 0, entity_id)

    # verify package channel exists but is disabled (index 3)
    validate_rtsps_camera_entity(hass, doorbell, 3)


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
    assert hass.states.get(entity_id)
    camera_obj = get_camera_from_entity_id(hass, entity_id)
    assert camera_obj.camera_capabilities == CameraCapabilities(
        {StreamType.HLS, StreamType.WEB_RTC}
    )


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
    # With all channels (high, medium, low), we get 3 entities total, 1 enabled
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)

    await remove_entities(hass, ufp, [camera1])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)
    await adopt_devices(hass, ufp, [camera1])
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)


async def test_adopt_non_camera_device_ignored(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test that adopting a non-camera device is ignored by camera platform."""
    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)
    data = ufp.entry.runtime_data

    # Send a light device directly via the adopt signal - should be ignored
    async_dispatcher_send(hass, data.adopt_signal, light)
    await hass.async_block_till_done()
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)


async def test_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Test retrieving camera image."""

    await init_entry(hass, ufp, [camera])
    # Camera with 3 channels (high, medium, low), only high enabled by default
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)

    ufp.api.get_public_api_camera_snapshot = AsyncMock()

    await async_get_image(hass, "camera.test_camera_high_resolution_channel")
    ufp.api.get_public_api_camera_snapshot.assert_called_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_package_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: ProtectCamera
) -> None:
    """Test retrieving package camera image."""

    await init_entry(hass, ufp, [doorbell])
    # All channels enabled via entity_registry_enabled_by_default fixture
    assert_entity_counts(hass, Platform.CAMERA, 4, 4)

    ufp.api.get_package_camera_snapshot = AsyncMock()

    await async_get_image(hass, "camera.test_camera_package_camera")
    ufp.api.get_package_camera_snapshot.assert_called_once()


async def test_camera_generic_update(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Tests generic entity update service."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)
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
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)
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
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)
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
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)
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
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)
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
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)
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


@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        ("enable_motion_detection", True),
        ("disable_motion_detection", False),
    ],
)
async def test_camera_motion_detection(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    service: str,
    expected_value: bool,
) -> None:
    """Test enabling/disabling motion detection on camera."""
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)
    entity_id = "camera.test_camera_high_resolution_channel"

    with patch_ufp_method(
        camera, "set_motion_detection", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "camera",
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mock_method.assert_called_once_with(expected_value)


async def test_camera_rtsps_not_authorized(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test camera handles NotAuthorized exception when fetching RTSPS streams."""
    with patch.object(
        ProtectCamera, "get_rtsps_streams", AsyncMock(side_effect=NotAuthorized)
    ):
        await init_entry(hass, ufp, [camera])

    assert "Cannot fetch RTSPS streams without API key" in caplog.text


async def test_camera_rtsps_client_error(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test camera handles ClientError exception when fetching RTSPS streams."""
    # Override the fixture mock to raise ClientError using object.__setattr__ for pydantic
    object.__setattr__(
        camera, "get_rtsps_streams", AsyncMock(side_effect=ClientError("test"))
    )

    with caplog.at_level(logging.DEBUG):
        await init_entry(hass, ufp, [camera])

    # Error is logged at DEBUG level during pre-fetch in async_setup
    assert "Error fetching RTSPS streams for" in caplog.text


async def test_camera_rtsps_cache_clear_on_none(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
) -> None:
    """Test that setting RTSPS streams to None clears the cache."""
    await init_entry(hass, ufp, [camera])
    data = ufp.entry.runtime_data

    # First set streams to a value
    mock_streams = create_mock_rtsps_streams(["high"])
    data.set_camera_rtsps_streams(camera.id, mock_streams)
    assert data.get_camera_rtsps_streams(camera.id) is not None

    # Now set to None to trigger the elif branch (line 122-123 in data.py)
    data.set_camera_rtsps_streams(camera.id, None)
    assert data.get_camera_rtsps_streams(camera.id) is None


async def test_camera_creates_repair_when_no_streams_available(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
) -> None:
    """Test camera creates repair issue when checked but no streams available."""
    # Mock get_rtsps_streams to return None (no active streams)
    object.__setattr__(camera, "get_rtsps_streams", AsyncMock(return_value=None))

    await init_entry(hass, ufp, [camera])

    # Verify repair issue was created for RTSP disabled
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{camera.id}")
    assert issue is not None


async def test_camera_creates_repair_when_cached_check_has_no_streams(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
) -> None:
    """Test repair issue created when camera is checked but no streams in cache.

    This tests the cached check path (line 153) where a camera has already
    been checked but has no available streams.
    """
    await init_entry(hass, ufp, [camera])
    data = ufp.entry.runtime_data

    # Clear the streams cache but keep the camera marked as checked
    data._camera_rtsps_streams.pop(camera.id, None)

    # Trigger a refresh via the streams signal (simulates reconnect or IP change)
    # This will hit the cached check path since camera is already marked as checked
    async_dispatcher_send(hass, data.streams_signal, camera.id)
    await hass.async_block_till_done()

    # Verify repair issue was created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{camera.id}")
    assert issue is not None


async def test_camera_handles_not_authorized_on_refresh(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test camera handles NotAuthorized during individual refresh (not pre-fetch).

    This tests line 265-271 - the NotAuthorized exception path when refreshing
    an individual camera that wasn't pre-fetched.
    """
    await init_entry(hass, ufp, [camera])
    data = ufp.entry.runtime_data

    # Clear the checked set so camera will attempt fresh fetch
    data._camera_rtsps_checked.discard(camera.id)

    # Mock the camera to raise NotAuthorized on next call
    object.__setattr__(
        camera, "get_rtsps_streams", AsyncMock(side_effect=NotAuthorized)
    )

    # Trigger a refresh - this should hit the NotAuthorized exception
    async_dispatcher_send(hass, data.streams_signal, camera.id)
    await hass.async_block_till_done()

    assert "Cannot fetch RTSPS streams without API key" in caplog.text
    # Camera should be marked as checked to prevent repeated calls
    assert data.is_camera_rtsps_checked(camera.id)


async def test_camera_handles_client_error_on_refresh(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test camera handles ClientError during individual refresh (not pre-fetch).

    This tests lines 272-275 - the ClientError/NvrError exception path when
    refreshing an individual camera.
    """
    await init_entry(hass, ufp, [camera])
    data = ufp.entry.runtime_data

    # Clear the checked set so camera will attempt fresh fetch
    data._camera_rtsps_checked.discard(camera.id)

    # Mock the camera to raise ClientError on next call
    object.__setattr__(
        camera, "get_rtsps_streams", AsyncMock(side_effect=ClientError("test"))
    )

    # Trigger a refresh - this should hit the ClientError exception
    async_dispatcher_send(hass, data.streams_signal, camera.id)
    await hass.async_block_till_done()

    assert "Error fetching RTSPS streams from public API" in caplog.text
    # Camera should be marked as checked to prevent repeated calls
    assert data.is_camera_rtsps_checked(camera.id)


async def test_camera_creates_repair_on_fresh_fetch_with_no_streams(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
) -> None:
    """Test repair issue created when fresh fetch returns no streams.

    This tests line 265 - the else branch after API fetch when streams is None.
    """
    await init_entry(hass, ufp, [camera])
    data = ufp.entry.runtime_data

    # Clear the checked set AND the streams cache so camera will attempt fresh fetch
    data._camera_rtsps_checked.discard(camera.id)
    data._camera_rtsps_streams.pop(camera.id, None)

    # Delete any existing repair issue first
    ir.async_delete_issue(hass, DOMAIN, f"rtsp_disabled_{camera.id}")

    # Mock the camera to return None (no streams)
    object.__setattr__(camera, "get_rtsps_streams", AsyncMock(return_value=None))

    # Trigger a refresh - this should create a repair issue
    async_dispatcher_send(hass, data.streams_signal, camera.id)
    await hass.async_block_till_done()

    # Verify repair issue was created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{camera.id}")
    assert issue is not None
