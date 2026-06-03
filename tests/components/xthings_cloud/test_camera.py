"""Tests for Xthings Cloud camera platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import WebRTCAnswer, WebRTCError, async_get_image
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


def _get_camera_entity(hass: HomeAssistant, entity_id: str):
    """Helper to retrieve a camera entity from hass data."""
    return hass.data[Platform.CAMERA].get_entity(entity_id)


async def test_cameras(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test camera entities are created correctly."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_camera_unavailable_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test camera shows unavailable when device is offline."""
    get_device_by_id(mock_api_client, "dev_camera_001")["online"] = False
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_camera_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test camera image fetching."""
    mock_api_client.async_get_snapshot.return_value = b"image_data"
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None

    image = await async_get_image(hass, "camera.front_door_camera")
    assert image.content == b"image_data"
    mock_api_client.async_get_snapshot.assert_called_once_with(
        "https://example.com/snapshot.jpg"
    )


async def test_updating_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
) -> None:
    """Test updating state and fetching new snapshot."""
    mock_api_client.async_get_snapshot.return_value = b"new_image_data"
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    assert mock_websocket.call_args is not None

    mock_websocket.call_args[1]["on_device_status"](
        "dev_camera_001",
        {
            "snapshot_url": "https://example.com/new_snapshot.jpg",
        },
    )

    await hass.async_block_till_done()

    mock_api_client.async_get_snapshot.assert_called_once_with(
        "https://example.com/new_snapshot.jpg"
    )


async def test_webrtc_offer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test WebRTC offer handling."""
    mock_api_client.async_get_camera_webrtc.return_value = {
        "region": "us-east-1",
        "channel_arn": "arn:aws:kinesisvideo:us-east-1:111111111111:channel/test/123",
        "viewer": {
            "AccessKeyId": "test",
            "SecretAccessKey": "test",
            "SessionToken": "test",
        },
    }
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    camera_entity = _get_camera_entity(hass, "camera.front_door_camera")
    assert camera_entity is not None

    with patch(
        "homeassistant.components.xthings_cloud.camera.KvsSignalingClient"
    ) as mock_kvs_client_class:
        mock_kvs_client = mock_kvs_client_class.return_value
        mock_kvs_client.async_get_answer_sdp = AsyncMock(return_value="mock_answer_sdp")

        mock_send_message = MagicMock()

        await camera_entity.async_handle_async_webrtc_offer(
            offer_sdp="mock_offer_sdp",
            session_id="mock_session_id",
            send_message=mock_send_message,
        )

        mock_api_client.async_get_camera_webrtc.assert_called_once_with(
            "dev_camera_001"
        )
        mock_kvs_client_class.assert_called_once()
        mock_kvs_client.async_get_answer_sdp.assert_called_once()

        mock_send_message.assert_called_once()
        call_arg = mock_send_message.call_args[0][0]
        assert isinstance(call_arg, WebRTCAnswer)
        assert call_arg.answer == "mock_answer_sdp"


async def test_webrtc_candidate_caching_and_flush(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test ICE candidate caching and flushing on offer."""
    mock_api_client.async_get_camera_webrtc.return_value = {
        "region": "us-east-1",
        "channel_arn": "arn:aws:kinesisvideo:us-east-1:111111111111:channel/test/123",
        "viewer": {
            "AccessKeyId": "test",
            "SecretAccessKey": "test",
            "SessionToken": "test",
        },
    }
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    camera_entity = _get_camera_entity(hass, "camera.front_door_camera")
    assert camera_entity is not None

    session_id = "mock_session_id"
    candidate = RTCIceCandidateInit(
        candidate="mock_candidate_string",
        sdp_mid="mock_sdp_mid",
        sdp_m_line_index=0,
    )

    # Call async_on_webrtc_candidate before session exists
    await camera_entity.async_on_webrtc_candidate(session_id, candidate)

    with patch(
        "homeassistant.components.xthings_cloud.camera.KvsSignalingClient"
    ) as mock_kvs_client_class:
        mock_kvs_client = mock_kvs_client_class.return_value
        mock_kvs_client.async_get_answer_sdp = AsyncMock(return_value="mock_answer_sdp")
        mock_kvs_client.async_send_ice_candidate = AsyncMock()

        await camera_entity.async_handle_async_webrtc_offer(
            offer_sdp="mock_offer_sdp",
            session_id=session_id,
            send_message=MagicMock(),
        )

        # Verify candidate was flushed to KVS client
        mock_kvs_client.async_send_ice_candidate.assert_called_once_with(
            candidate="mock_candidate_string",
            sdp_mid="mock_sdp_mid",
            sdp_m_line_index=0,
        )

        # Re-send candidate after session is established to verify direct send
        await camera_entity.async_on_webrtc_candidate(session_id, candidate)
        assert mock_kvs_client.async_send_ice_candidate.call_count == 2


async def test_webrtc_session_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test WebRTC session cleanup clears cache and closes client."""
    mock_api_client.async_get_camera_webrtc.return_value = {
        "region": "us-east-1",
        "channel_arn": "arn:aws:kinesisvideo:us-east-1:111111111111:channel/test/123",
        "viewer": {
            "AccessKeyId": "test",
            "SecretAccessKey": "test",
            "SessionToken": "test",
        },
    }
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    camera_entity = _get_camera_entity(hass, "camera.front_door_camera")
    assert camera_entity is not None

    session_id = "mock_session_id"
    candidate = RTCIceCandidateInit(
        candidate="mock_candidate_string",
        sdp_mid="mock_sdp_mid",
        sdp_m_line_index=0,
    )

    await camera_entity.async_on_webrtc_candidate(session_id, candidate)

    with patch(
        "homeassistant.components.xthings_cloud.camera.KvsSignalingClient"
    ) as mock_kvs_client_class:
        mock_kvs_client = mock_kvs_client_class.return_value
        mock_kvs_client.async_get_answer_sdp = AsyncMock(return_value="mock_answer_sdp")
        mock_kvs_client.async_close = AsyncMock()

        await camera_entity.async_handle_async_webrtc_offer(
            offer_sdp="mock_offer_sdp",
            session_id=session_id,
            send_message=MagicMock(),
        )

        # Test close_webrtc_session
        camera_entity.close_webrtc_session(session_id)

        await hass.async_block_till_done()
        mock_kvs_client.async_close.assert_called_once()

        # Verify that candidate is not flushed after session is closed
        mock_kvs_client.async_send_ice_candidate = AsyncMock()
        await camera_entity.async_on_webrtc_candidate(session_id, candidate)
        mock_kvs_client.async_send_ice_candidate.assert_not_called()


async def test_webrtc_offer_kvs_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test WebRTC offer handling failure paths."""
    mock_api_client.async_get_camera_webrtc.return_value = {
        "region": "us-east-1",
        "channel_arn": None,
    }
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    camera_entity = _get_camera_entity(hass, "camera.front_door_camera")
    assert camera_entity is not None

    mock_send_message = MagicMock()

    await camera_entity.async_handle_async_webrtc_offer(
        offer_sdp="mock_offer_sdp",
        session_id="mock_session_id",
        send_message=mock_send_message,
    )

    mock_send_message.assert_called_once()
    call_arg = mock_send_message.call_args[0][0]
    assert isinstance(call_arg, WebRTCError)
    assert call_arg.code == "kvs_error"
