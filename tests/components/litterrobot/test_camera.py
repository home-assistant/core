"""Test the Litter-Robot camera entity."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pylitterbot.camera import CameraSession
from pylitterbot.exceptions import CameraNotAvailableException, CameraStreamException
import pytest
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    WebRTCAnswer,
    WebRTCCandidate,
)
from homeassistant.components.litterrobot.camera import _build_ice_servers
from homeassistant.components.litterrobot.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import create_mock_robot, setup_integration

from tests.common import async_fire_time_changed

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
    # nothing is streaming until a viewer connects
    assert camera.state == "idle"


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
    """An offer relays signaling both ways; closing the session tears it down."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    assert entity is not None

    started_with = CameraSession.from_response(
        {**MOCK_SESSION_DATA, "sessionId": "started-session"}
    )

    async def start(offer_sdp, on_answer, on_candidate):
        on_answer("answer-sdp")
        on_candidate({"candidate": "candidate:a", "sdpMid": "1", "sdpMLineIndex": 2})
        # a candidate without the optional fields gets the defaults
        on_candidate({})
        return started_with

    relay = MagicMock()
    relay.start = AsyncMock(side_effect=start)
    relay.send_candidate = AsyncMock()
    relay.close = AsyncMock()
    send_message = MagicMock()

    with patch(
        "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
        return_value=relay,
    ):
        await entity.async_handle_async_webrtc_offer(
            "offer-sdp", "session-1", send_message
        )
    assert relay.start.call_args.args[0] == "offer-sdp"
    assert "session-1" in entity._relays
    assert entity._cached_session is started_with

    assert send_message.call_args_list[0].args[0] == WebRTCAnswer(answer="answer-sdp")
    assert send_message.call_args_list[1].args[0] == WebRTCCandidate(
        RTCIceCandidateInit(candidate="candidate:a", sdp_mid="1", sdp_m_line_index=2)
    )
    assert send_message.call_args_list[2].args[0] == WebRTCCandidate(
        RTCIceCandidateInit(candidate="", sdp_mid="0", sdp_m_line_index=0)
    )
    assert hass.states.get(CAMERA_ENTITY_ID).state == "streaming"

    # a browser candidate for a live session is forwarded to its relay
    await entity.async_on_webrtc_candidate(
        "session-1",
        RTCIceCandidateInit(
            candidate="candidate:1 1 udp 2130706431 192.0.2.1 3478 typ host",
            sdp_mid="1",
            sdp_m_line_index=3,
        ),
    )
    relay.send_candidate.assert_awaited_once_with(
        {
            "candidate": "candidate:1 1 udp 2130706431 192.0.2.1 3478 typ host",
            "sdpMid": "1",
            "sdpMLineIndex": 3,
        }
    )

    # missing mid and index fall back to the first media section
    await entity.async_on_webrtc_candidate(
        "session-1", RTCIceCandidateInit(candidate="candidate:2")
    )
    assert relay.send_candidate.await_args.args[0] == {
        "candidate": "candidate:2",
        "sdpMid": "0",
        "sdpMLineIndex": 0,
    }

    entity.close_webrtc_session("session-1")
    await hass.async_block_till_done()
    assert "session-1" not in entity._relays
    relay.close.assert_awaited_once()
    assert hass.states.get(CAMERA_ENTITY_ID).state == "idle"


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


async def test_camera_image_returns_placeholder(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """No snapshot endpoint exists, so a placeholder still is served."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    image = await entity.async_camera_image()
    # returning None here would make every thumbnail request raise
    # "Unable to get image"
    assert image is not None
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    # the placeholder is a png; the base class would otherwise claim jpeg
    assert entity.content_type == "image/png"


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
    relay.start = AsyncMock(side_effect=CameraStreamException("signaling refused"))

    with (
        patch(
            "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
            return_value=relay,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await entity.async_handle_async_webrtc_offer(
            "v=0\r\n", "session-fail", MagicMock()
        )

    assert exc_info.value.translation_key == "camera_stream_failed"
    assert exc_info.value.translation_placeholders == {"error": "signaling refused"}
    assert "session-fail" not in entity._relays
    assert hass.states.get(CAMERA_ENTITY_ID).state == "idle"


async def test_webrtc_offer_cancelled_drops_the_relay(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """A client that disconnects mid-offer leaves no relay behind."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    relay = MagicMock()
    relay.start = AsyncMock(side_effect=asyncio.CancelledError)

    with (
        patch(
            "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
            return_value=relay,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await entity.async_handle_async_webrtc_offer(
            "v=0\r\n", "session-cancel", MagicMock()
        )

    assert "session-cancel" not in entity._relays


async def test_webrtc_offer_without_a_camera_client(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """A robot that can no longer provide a camera client reports it."""
    robot = mock_account_with_litterrobot_5_pro.robots[0]
    robot.get_camera_client().generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    robot.get_camera_client = MagicMock(
        side_effect=CameraNotAvailableException("no camera")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_handle_async_webrtc_offer("v=0\r\n", "s", MagicMock())

    assert exc_info.value.translation_key == "camera_not_available"
    assert exc_info.value.translation_placeholders == {"error": "no camera"}


async def test_viewer_leaving_during_the_offer_does_not_leak_the_relay(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """A session closed while start() connects must not be left running."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    cached = entity._cached_session

    async def start(offer_sdp, on_answer, on_candidate):
        # the browser closes the dialog while the relay is still connecting
        entity.close_webrtc_session("session-gone")
        return CameraSession.from_response(
            {**MOCK_SESSION_DATA, "sessionId": "late-session"}
        )

    relay = MagicMock()
    relay.start = AsyncMock(side_effect=start)
    relay.close = AsyncMock()

    with patch(
        "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
        return_value=relay,
    ):
        await entity.async_handle_async_webrtc_offer(
            "v=0\r\n", "session-gone", MagicMock()
        )
    await hass.async_block_till_done()

    # closed again once start() returned, so its websocket and tasks are not
    # left running with no owner
    assert relay.close.await_count == 2
    assert "session-gone" not in entity._relays
    assert entity._cached_session is cached
    assert hass.states.get(CAMERA_ENTITY_ID).state == "idle"


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

    before = mock_client.generate_session.call_count
    config = entity._async_get_webrtc_client_configuration()
    # stale TURN credentials are withheld rather than served
    assert config.configuration.ice_servers == []
    # exactly one replacement is fetched
    assert mock_client.generate_session.call_count == before + 1

    await hass.async_block_till_done()
    assert entity._cached_session is not None


async def test_empty_cache_is_refetched_on_a_configuration_request(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """With no session cached, a request retries rather than staying empty."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    entity._cached_session = None
    before = mock_client.generate_session.call_count

    config = entity._async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == []
    assert mock_client.generate_session.call_count == before + 1

    await hass.async_block_till_done()
    assert entity._cached_session is not None
    # the next client gets the credentials
    config = entity._async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers != []


async def test_removal_awaits_relay_teardown(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """Relays are closed before the entity goes away, not left to a task."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    relay = MagicMock()
    # the real start() returns the session the camera was started with
    relay.start = AsyncMock(return_value=CameraSession.from_response(MOCK_SESSION_DATA))
    relay.close = AsyncMock()

    with patch(
        "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
        return_value=relay,
    ):
        await entity.async_handle_async_webrtc_offer(
            "v=0\r\n", "session-teardown", MagicMock()
        )

    await entity.async_will_remove_from_hass()
    # closed by the time removal returns, without needing the event loop to
    # run a scheduled task afterwards
    assert relay.close.called
    assert entity._relays == {}


async def test_session_is_not_renewed_in_the_background(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5_pro: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An idle camera must not keep creating sessions.

    Guards against reintroducing a renewal timer. Sessions are short-lived, so
    renewing one ahead of its expiry would create a new camera session every
    few minutes, whether or not anyone is watching.
    """
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    # expires inside the interval advanced below, so a renewal scheduled
    # before expiry, or after it, would fire
    expires = (dt_util.utcnow() + timedelta(seconds=60)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(
            {**MOCK_SESSION_DATA, "sessionExpiration": expires}
        )
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)
    fetched = mock_client.generate_session.call_count

    freezer.tick(timedelta(hours=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_client.generate_session.call_count == fetched


async def test_camera_added_for_a_robot_discovered_after_setup(
    hass: HomeAssistant,
    mock_account_with_no_robots: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A camera robot that appears after setup gets its entity without a reload."""
    await setup_integration(hass, mock_account_with_no_robots, CAMERA_DOMAIN)
    assert hass.states.get(CAMERA_ENTITY_ID) is None

    robot = create_mock_robot(
        None,
        mock_account_with_no_robots,
        v4=False,
        v5=False,
        v5_pro=True,
        feeder=False,
    )
    robot.get_camera_client().generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    mock_account_with_no_robots.robots.append(robot)

    freezer.tick(timedelta(seconds=305))  # the coordinator's 5 minute refresh
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(CAMERA_ENTITY_ID) is not None

    # a later refresh must not add it a second time
    freezer.tick(timedelta(seconds=305))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 1


async def test_failed_session_fetch_leaves_the_entity_usable(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """A failed fetch only costs the TURN servers, and the next request retries."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        side_effect=CameraStreamException("no session")
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    assert hass.states.get(CAMERA_ENTITY_ID) is not None
    assert entity._cached_session is None
    config = entity._async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers == []

    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await hass.async_block_till_done()
    entity._async_get_webrtc_client_configuration()
    await hass.async_block_till_done()
    config = entity._async_get_webrtc_client_configuration()
    assert config.configuration.ice_servers != []


async def test_concurrent_requests_fetch_one_session(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """Requests arriving while a fetch is running do not start another."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    release = asyncio.Event()

    async def slow_session(auto_start: bool):
        await release.wait()
        return CameraSession.from_response(MOCK_SESSION_DATA)

    mock_client.generate_session = AsyncMock(side_effect=slow_session)
    entity._cached_session = None

    entity._async_get_webrtc_client_configuration()
    entity._async_get_webrtc_client_configuration()
    entity._async_get_webrtc_client_configuration()
    release.set()
    await hass.async_block_till_done()

    assert mock_client.generate_session.call_count == 1


def test_ice_servers_turn_url_as_a_string() -> None:
    """A bare turnUrl string is wrapped, and the stun url follows it."""
    (server,) = _build_ice_servers(
        _session(
            {
                "turnUrl": "turn:turn.example.com:443",
                "stunUrl": "stun:stun.example.com:3478",
            }
        )
    )
    assert server.urls == ["turn:turn.example.com:443", "stun:stun.example.com:3478"]


def test_ice_servers_empty_urls_fall_back_to_turn_url() -> None:
    """An empty "urls" list does not hide the Watford fields."""
    (server,) = _build_ice_servers(
        _session({"urls": [], "turnUrl": ["turn:turn.example.com:443"]})
    )
    assert server.urls == ["turn:turn.example.com:443"]


def test_ice_servers_multiple_credentials() -> None:
    """Every credential with a url becomes its own server."""
    servers = _build_ice_servers(
        _session(
            {"urls": ["turn:a.example.com"], "username": "a", "credential": "x"},
            {"username": "no-url"},
            {"urls": ["turn:b.example.com"], "username": "b", "credential": "y"},
        )
    )
    assert [server.username for server in servers] == ["a", "b"]


async def test_unloading_closes_open_relays(
    hass: HomeAssistant, mock_account_with_litterrobot_5_pro: MagicMock
) -> None:
    """Unloading the integration tears down live streams."""
    mock_client = mock_account_with_litterrobot_5_pro.robots[0].get_camera_client()
    mock_client.generate_session = AsyncMock(
        return_value=CameraSession.from_response(MOCK_SESSION_DATA)
    )
    await setup_integration(hass, mock_account_with_litterrobot_5_pro, CAMERA_DOMAIN)

    entity = hass.data[CAMERA_DOMAIN].get_entity(CAMERA_ENTITY_ID)
    relay = MagicMock()
    relay.start = AsyncMock(return_value=CameraSession.from_response(MOCK_SESSION_DATA))
    relay.close = AsyncMock()
    with patch(
        "homeassistant.components.litterrobot.camera.CameraSignalingRelay",
        return_value=relay,
    ):
        await entity.async_handle_async_webrtc_offer("v=0\r\n", "live", MagicMock())

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    relay.close.assert_awaited_once()
