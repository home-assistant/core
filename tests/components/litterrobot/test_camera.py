"""Test the Litter-Robot camera entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from pylitterbot.camera import CameraSession

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

# the LR5 Pro fixture's robot is named "Test Pro", not "Test"
CAMERA_ENTITY_ID = "camera.test_pro_camera"

MOCK_SESSION_DATA = {
    "sessionId": "test-session-id",
    "sessionToken": "test-session-token",
    # far future on purpose: a fixed near date silently flips these tests
    # onto the expired-session branch once it passes
    "sessionExpiration": "2099-12-31T23:59:59.000000Z",
    "turnCredentials": [
        {
            "urls": ["turn:turn.example.com:443?transport=tcp"],
            "username": "turn-user",
            "credential": "turn-pass",
        }
    ],
}


async def test_camera_entity_created(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """Test camera entity is created for LR5 Pro."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    camera = hass.states.get(CAMERA_ENTITY_ID)
    assert camera is not None
    assert camera.state == "streaming"


async def test_camera_not_created_for_standard_lr5(
    hass: HomeAssistant, mock_account_with_litterrobot_5: MagicMock
) -> None:
    """Test camera entity is not created for standard LR5 (no camera)."""
    await setup_integration(hass, mock_account_with_litterrobot_5, CAMERA_DOMAIN)

    # assert on the domain rather than a guessed entity id: a wrong id would
    # make this pass whether or not an entity was created
    assert not hass.states.async_entity_ids(CAMERA_DOMAIN)


async def test_camera_not_created_for_lr3(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Test camera entity is not created for LR3."""
    await setup_integration(hass, mock_account, CAMERA_DOMAIN)

    assert not hass.states.async_entity_ids(CAMERA_DOMAIN)


async def test_webrtc_offer_relays_and_cleans_up(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """An offer opens a relay; closing the session tears it down."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    component = hass.data[CAMERA_DOMAIN]
    entity = component.get_entity(CAMERA_ENTITY_ID)
    assert entity is not None

    relay = MagicMock()
    relay.start = AsyncMock()
    relay.send_candidate = AsyncMock()
    relay.close = AsyncMock()
    send_message = MagicMock()

    with patch(
        "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
        return_value=relay,
    ):
        await entity.async_handle_async_webrtc_offer(
            "v=0\r\n", "session-1", send_message
        )
    assert "session-1" in entity._relays

    # a candidate for a live session is forwarded to its relay
    candidate = MagicMock()
    candidate.candidate = "candidate:1 1 udp 2130706431 192.0.2.1 3478 typ host"
    candidate.sdp_mid = "0"
    candidate.sdp_m_line_index = 0
    await entity.async_on_webrtc_candidate("session-1", candidate)
    assert relay.send_candidate.called

    entity.close_webrtc_session("session-1")
    await hass.async_block_till_done()
    assert "session-1" not in entity._relays
    assert relay.close.called


async def test_webrtc_candidate_for_unknown_session_is_ignored(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """A candidate arriving after teardown must not raise."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    candidate = MagicMock()
    candidate.candidate = "candidate:1 1 udp 2130706431 192.0.2.1 3478 typ host"
    candidate.sdp_mid = "0"
    candidate.sdp_m_line_index = 0
    await entity.async_on_webrtc_candidate("never-opened", candidate)


async def test_camera_image_returns_none(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """The device has no snapshot endpoint, so no still is offered."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    assert await entity.async_camera_image() is None
