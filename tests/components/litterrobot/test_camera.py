"""Test the Litter-Robot camera entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from pylitterbot.camera import CameraSession
import pytest

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.litterrobot.camera import _build_ice_servers
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


def _session(*creds: dict) -> CameraSession:
    """Build a CameraSession carrying the given TURN credential dicts."""
    return CameraSession.from_response({**MOCK_SESSION_DATA, "turnCredentials": creds})


def test_ice_servers_standard_format() -> None:
    """The documented format maps straight through."""
    (server,) = _build_ice_servers(
        _session(
            {
                "urls": ["turn:turn.example.com:443"],
                "username": "turn-user",
                "credential": "turn-pass",
            }
        )
    )
    assert server.urls == ["turn:turn.example.com:443"]
    assert server.username == "turn-user"
    assert server.credential == "turn-pass"


def test_ice_servers_uris_key_and_string_url() -> None:
    """A bare "uris" string is accepted and wrapped into a list."""
    (server,) = _build_ice_servers(_session({"uris": "turn:turn.example.com:443"}))
    assert server.urls == ["turn:turn.example.com:443"]
    # absent credentials become empty strings rather than None
    assert server.username == ""
    assert server.credential == ""


def test_ice_servers_watford_format() -> None:
    """The Watford variant supplies turnUrl/stunUrl and "password"."""
    (server,) = _build_ice_servers(
        _session(
            {
                "turnUrl": ["turn:turn.example.com:443"],
                "stunUrl": "stun:stun.example.com:3478",
                "username": "turn-user",
                "password": "turn-pass",
            }
        )
    )
    assert server.urls == [
        "turn:turn.example.com:443",
        "stun:stun.example.com:3478",
    ]
    assert server.credential == "turn-pass"


def test_ice_servers_does_not_mutate_session() -> None:
    """Sessions are cached and reused, so building must not append in place."""
    session = _session(
        {
            "turnUrl": ["turn:turn.example.com:443"],
            "stunUrl": "stun:stun.example.com:3478",
        }
    )
    # copy: both calls would otherwise hand back the same mutated list object
    # and compare equal to itself
    first = list(_build_ice_servers(session)[0].urls)
    second = list(_build_ice_servers(session)[0].urls)
    assert first == second
    assert session.turn_servers[0]["turnUrl"] == ["turn:turn.example.com:443"]


def test_ice_servers_skips_entries_without_urls() -> None:
    """A credential carrying no usable url contributes no server."""
    assert _build_ice_servers(_session({"username": "turn-user"})) == []


async def test_webrtc_offer_failure_drops_the_relay(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """A relay that fails to start is not left behind in the session map."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    relay = MagicMock()
    relay.start = AsyncMock(side_effect=Exception("signaling refused"))

    with (
        patch(
            "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
            return_value=relay,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_handle_async_webrtc_offer(
            "v=0\r\n", "session-fail", MagicMock()
        )

    assert "session-fail" not in entity._relays


async def test_expired_session_offers_no_ice_servers(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """An expired session is dropped, not served as stale TURN credentials."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    entity._cached_session = CameraSession.from_response(
        {**MOCK_SESSION_DATA, "sessionExpiration": "2020-01-01T00:00:00.000000Z"}
    )

    config = entity._async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == []
    # dropped immediately so repeated requests do not queue a refresh each time
    assert entity._cached_session is None

    await hass.async_block_till_done()
