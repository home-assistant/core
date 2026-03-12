"""Test the UniFi Protect camera platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import AiPort, Camera as ProtectCamera, CameraChannel, StateType
from uiprotect.exceptions import NvrError
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
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
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
from homeassistant.setup import async_setup_component

from . import patch_ufp_method
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

    ufp.api.get_public_api_camera_snapshot = AsyncMock()

    await async_get_image(hass, "camera.test_camera_high_resolution_channel")
    ufp.api.get_public_api_camera_snapshot.assert_called_once()


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

    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    state = hass.states.get(entity_id)
    assert state and state.state == "idle"

    ufp.api.update = AsyncMock(return_value=None)
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
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
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)
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


async def test_aiport_no_camera_entities(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    aiport: AiPort,
) -> None:
    """Test that AI Port devices do not create camera entities."""
    await init_entry(hass, ufp, [aiport])

    # AI Port should not create any camera entities
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)


async def test_aiport_rtsp_issue_cleanup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    aiport: AiPort,
) -> None:
    """Test that RTSP disabled issues for AI Ports are cleaned up on setup."""
    # Set up the integration with the AI Port first
    # (init_entry regenerates IDs, so we need to get the new ID)
    await init_entry(hass, ufp, [aiport])

    # Now get the actual AI Port ID after regeneration
    actual_aiport_id = aiport.id

    # Create an RTSP disabled issue for the AI Port
    # (simulating an issue that might have been created by a previous buggy version)
    issue_id = f"rtsp_disabled_{actual_aiport_id}"

    # Get the issue registry and create the issue directly via internal method
    # to avoid translation validation (as we're simulating a legacy issue)
    issue_registry = ir.async_get(hass)
    issue_registry.issues[(DOMAIN, issue_id)] = ir.IssueEntry(
        active=True,
        breaks_in_ha_version=None,
        created=None,
        data=None,
        dismissed_version=None,
        domain=DOMAIN,
        is_fixable=True,
        is_persistent=False,
        issue_domain=None,
        issue_id=issue_id,
        learn_more_url=None,
        severity=ir.IssueSeverity.WARNING,
        translation_key="rtsp_disabled",
        translation_placeholders=None,
    )

    # Verify the issue exists
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    # Reload the integration - this should clean up the issue
    await hass.config_entries.async_reload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    # The issue should be cleaned up since AI Ports can't have RTSP
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    # Verify no camera entities were created
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)
