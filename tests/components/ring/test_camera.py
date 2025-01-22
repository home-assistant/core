"""The tests for the Ring switch platform."""

import logging
from unittest.mock import AsyncMock, Mock, patch

from aiohttp.test_utils import make_mocked_request
from freezegun.api import FrozenDateTimeFactory
import pytest
import ring_doorbell
from ring_doorbell.webrtcstream import RingWebRtcMessage
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    CameraEntityFeature,
    StreamType,
    async_get_image,
    async_get_mjpeg_stream,
    get_camera_from_entity_id,
)
from homeassistant.components.ring.camera import FORCE_REFRESH_INTERVAL
from homeassistant.components.ring.const import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.aiohttp import MockStreamReader

from .common import MockConfigEntry, setup_platform
from .device_mocks import FRONT_DEVICE_ID

from tests.common import async_fire_time_changed, snapshot_platform
from tests.typing import WebSocketGenerator

SMALLEST_VALID_JPEG = (
    "ffd8ffe000104a46494600010101004800480000ffdb00430003020202020203020202030303030406040404040408060"
    "6050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b08000100"
    "0101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)
SMALLEST_VALID_JPEG_BYTES = bytes.fromhex(SMALLEST_VALID_JPEG)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_states(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_config_entry.add_to_hass(hass)
    # Patch getrandbits so the access_token doesn't change on camera attributes
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_platform(hass, Platform.CAMERA)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_name", "expected_state", "friendly_name"),
    [
        ("camera.internal_last_recording", True, "Internal Last recording"),
        ("camera.front_last_recording", None, "Front Last recording"),
    ],
    ids=["On", "Off"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_motion_detection_state_reports_correctly(
    hass: HomeAssistant,
    mock_ring_client,
    entity_name,
    expected_state,
    friendly_name,
) -> None:
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get(entity_name)
    assert state.attributes.get("motion_detection") is expected_state
    assert state.attributes.get("friendly_name") == friendly_name


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_motion_detection_can_be_turned_on_and_off(
    hass: HomeAssistant,
    mock_ring_client,
) -> None:
    """Tests the siren turns on correctly."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get("camera.front_last_recording")
    assert state.attributes.get("motion_detection") is not True

    await hass.services.async_call(
        "camera",
        "enable_motion_detection",
        {"entity_id": "camera.front_last_recording"},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get("camera.front_last_recording")
    assert state.attributes.get("motion_detection") is True

    await hass.services.async_call(
        "camera",
        "disable_motion_detection",
        {"entity_id": "camera.front_last_recording"},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get("camera.front_last_recording")
    assert state.attributes.get("motion_detection") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_motion_detection_not_supported(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests the siren turns on correctly."""
    front_camera_mock = mock_ring_devices.get_device(765432)
    has_capability = front_camera_mock.has_capability.side_effect

    def _has_capability(capability):
        if capability == "motion_detection":
            return False
        return has_capability(capability)

    front_camera_mock.has_capability.side_effect = _has_capability

    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get("camera.front_last_recording")
    assert state.attributes.get("motion_detection") is None

    await hass.services.async_call(
        "camera",
        "enable_motion_detection",
        {"entity_id": "camera.front_last_recording"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("camera.front_last_recording")
    assert state.attributes.get("motion_detection") is None
    assert (
        "Entity camera.front_last_recording does not have motion detection capability"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("exception_type", "reauth_expected"),
    [
        (ring_doorbell.AuthenticationError, True),
        (ring_doorbell.RingTimeout, False),
        (ring_doorbell.RingError, False),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_motion_detection_errors_when_turned_on(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    exception_type,
    reauth_expected,
) -> None:
    """Tests the motion detection errors are handled correctly."""
    await setup_platform(hass, Platform.CAMERA)
    config_entry = hass.config_entries.async_entries("ring")[0]

    assert not any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    front_camera_mock = mock_ring_devices.get_device(765432)
    front_camera_mock.async_set_motion_detection.side_effect = exception_type

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "camera",
            "enable_motion_detection",
            {"entity_id": "camera.front_last_recording"},
            blocking=True,
        )
    await hass.async_block_till_done()
    front_camera_mock.async_set_motion_detection.assert_called_once()
    assert (
        any(
            flow
            for flow in config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
            if flow["handler"] == "ring"
        )
        == reauth_expected
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_handle_mjpeg_stream(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera returns handle mjpeg stream when available."""
    await setup_platform(hass, Platform.CAMERA)

    front_camera_mock = mock_ring_devices.get_device(765432)
    front_camera_mock.async_recording_url.return_value = None

    state = hass.states.get("camera.front_last_recording")
    assert state is not None

    mock_request = make_mocked_request("GET", "/", headers={"token": "x"})

    # history not updated yet
    front_camera_mock.async_history.assert_not_called()
    front_camera_mock.async_recording_url.assert_not_called()
    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.front_last_recording"
    )
    assert stream is None

    # Video url will be none so no  stream
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_history.assert_called_once()
    front_camera_mock.async_recording_url.assert_called()

    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.front_last_recording"
    )
    assert stream is None

    # Stop the history updating so we can update the values manually
    front_camera_mock.async_history = AsyncMock()
    front_camera_mock.last_history[0]["recording"]["status"] = "not ready"
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_recording_url.assert_called()
    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.front_last_recording"
    )
    assert stream is None

    # If the history id hasn't changed the camera will not check again for the video url
    # until the FORCE_REFRESH_INTERVAL has passed
    front_camera_mock.last_history[0]["recording"]["status"] = "ready"
    front_camera_mock.async_recording_url = AsyncMock(return_value="http://dummy.url")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_recording_url.assert_not_called()

    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.front_last_recording"
    )
    assert stream is None

    freezer.tick(FORCE_REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_recording_url.assert_called()

    # Now the stream should be returned
    stream_reader = MockStreamReader(SMALLEST_VALID_JPEG_BYTES)
    with patch("homeassistant.components.ring.camera.CameraMjpeg") as mock_camera:
        mock_camera.return_value.get_reader = AsyncMock(return_value=stream_reader)
        mock_camera.return_value.open_camera = AsyncMock()
        mock_camera.return_value.close = AsyncMock()

        stream = await async_get_mjpeg_stream(
            hass, mock_request, "camera.front_last_recording"
        )
        assert stream is not None
        # Check the stream has been read
        assert not await stream_reader.read(-1)


async def test_camera_image(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera will return still image when available."""
    await setup_platform(hass, Platform.CAMERA)

    front_camera_mock = mock_ring_devices.get_device(765432)

    state = hass.states.get("camera.front_live_view")
    assert state is not None

    # history not updated yet
    front_camera_mock.async_history.assert_not_called()
    front_camera_mock.async_recording_url.assert_not_called()
    with (
        patch(
            "homeassistant.components.ring.camera.ffmpeg.async_get_image",
            return_value=SMALLEST_VALID_JPEG_BYTES,
        ),
        pytest.raises(HomeAssistantError),
    ):
        image = await async_get_image(hass, "camera.front_live_view")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    # history updated so image available
    front_camera_mock.async_history.assert_called_once()
    front_camera_mock.async_recording_url.assert_called_once()

    with patch(
        "homeassistant.components.ring.camera.ffmpeg.async_get_image",
        return_value=SMALLEST_VALID_JPEG_BYTES,
    ):
        image = await async_get_image(hass, "camera.front_live_view")
        assert image.content == SMALLEST_VALID_JPEG_BYTES


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_stream_attributes(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test stream attributes."""
    await setup_platform(hass, Platform.CAMERA)

    # Live view
    state = hass.states.get("camera.front_live_view")
    supported_features = state.attributes.get("supported_features")
    assert supported_features is CameraEntityFeature.STREAM
    camera = get_camera_from_entity_id(hass, "camera.front_live_view")
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.WEB_RTC}

    # Last recording
    state = hass.states.get("camera.front_last_recording")
    supported_features = state.attributes.get("supported_features")
    assert supported_features is CameraEntityFeature(0)
    camera = get_camera_from_entity_id(hass, "camera.front_last_recording")
    assert camera.camera_capabilities.frontend_stream_types == set()


async def test_camera_webrtc(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_ring_devices,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test WebRTC interactions."""
    caplog.set_level(logging.ERROR)
    await setup_platform(hass, Platform.CAMERA)
    client = await hass_ws_client(hass)

    # sdp offer
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": "camera.front_live_view",
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()
    assert response
    assert response.get("success") is True
    subscription_id = response["id"]
    assert not caplog.text

    front_camera_mock = mock_ring_devices.get_device(FRONT_DEVICE_ID)
    front_camera_mock.generate_async_webrtc_stream.assert_called_once()
    args = front_camera_mock.generate_async_webrtc_stream.call_args.args
    session_id = args[1]
    on_message = args[2]

    # receive session
    response = await client.receive_json()
    event = response.get("event")
    assert event
    assert event.get("type") == "session"
    assert not caplog.text

    # Ring candidate
    on_message(RingWebRtcMessage(candidate="candidate", sdp_m_line_index=1))
    response = await client.receive_json()
    event = response.get("event")
    assert event
    assert event.get("type") == "candidate"
    assert not caplog.text

    # Error message
    on_message(RingWebRtcMessage(error_code=1, error_message="error"))
    response = await client.receive_json()
    event = response.get("event")
    assert event
    assert event.get("type") == "error"
    assert not caplog.text

    # frontend candidate
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": "camera.front_live_view",
            "session_id": session_id,
            "candidate": {"candidate": "candidate", "sdpMLineIndex": 1},
        }
    )
    response = await client.receive_json()
    assert response
    assert response.get("success") is True
    assert not caplog.text
    front_camera_mock.on_webrtc_candidate.assert_called_once()

    # Invalid frontend candidate
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": "camera.front_live_view",
            "session_id": session_id,
            "candidate": {"candidate": "candidate", "sdpMid": "1"},
        }
    )
    response = await client.receive_json()
    assert response
    assert response.get("success") is False
    assert response["error"]["code"] == "home_assistant_error"
    msg = "The sdp_m_line_index is required for ring webrtc streaming"
    assert msg in response["error"].get("message")
    assert msg in caplog.text
    front_camera_mock.on_webrtc_candidate.assert_called_once()

    # Answer message
    caplog.clear()
    on_message(RingWebRtcMessage(answer="v=0\r\n"))
    response = await client.receive_json()
    event = response.get("event")
    assert event
    assert event.get("type") == "answer"
    assert not caplog.text

    # Unsubscribe/Close session
    front_camera_mock.sync_close_webrtc_stream.assert_not_called()
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": subscription_id,
        }
    )

    response = await client.receive_json()
    assert response
    assert response.get("success") is True
    front_camera_mock.sync_close_webrtc_stream.assert_called_once()
