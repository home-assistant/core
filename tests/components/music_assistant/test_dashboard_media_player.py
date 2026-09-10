"""Test Music Assistant dashboard display media player entities."""

from base64 import b64encode
import dataclasses
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

from music_assistant_models.dashboard import DashboardDevice, DashboardSession
from music_assistant_models.enums import DashboardType, EventType
from music_assistant_models.player import PlayerMedia
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
)
from homeassistant.components.music_assistant.const import ATTR_URL, DOMAIN
from homeassistant.components.music_assistant.services import SERVICE_PLAY_ANNOUNCEMENT
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    setup_dashboards,
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, WebSocketGenerator

KITCHEN_ENTITY_ID = "media_player.kitchen_display"
HALLWAY_ENTITY_ID = "media_player.hallway_display"
UNMAPPED_ENTITY_ID = "media_player.unmapped_player_display"

PROVIDER_ICON_BYTES = b"<svg/>"
PROVIDER_ICON_CONTENT_TYPE = "image/svg+xml"
PROVIDER_ICON_DATA_URI = (
    f"data:{PROVIDER_ICON_CONTENT_TYPE};base64,"
    f"{b64encode(PROVIDER_ICON_BYTES).decode()}"
)


def _mock_provider_icon(music_assistant_client: MagicMock) -> None:
    """Make providers/icon return a real data URI; other commands keep returning None."""

    async def send_command(command: str, **kwargs: Any) -> Any:
        if command == "providers/icon":
            return PROVIDER_ICON_DATA_URI
        return None

    music_assistant_client.send_command = AsyncMock(side_effect=send_command)


def _get_dashboard_entity(hass: HomeAssistant, entity_id: str) -> Any:
    """Return the dashboard entity instance for direct image method calls."""
    entity_component = hass.data["entity_components"][MEDIA_PLAYER_DOMAIN]
    return entity_component.get_entity(entity_id)


def _dashboards_event_data(music_assistant_client: MagicMock) -> list[dict]:
    """Build the DASHBOARDS_UPDATED event payload for the cache's current state."""
    return [
        dashboard.to_dict()
        for dashboard in music_assistant_client.dashboard._dashboards.values()
    ]


def _sessions_event_data(music_assistant_client: MagicMock) -> list[dict]:
    """Build the DASHBOARD_SESSIONS_UPDATED event payload for the cache's current state."""
    return [
        session.to_dict()
        for session in music_assistant_client.dashboard._sessions.values()
    ]


async def _play_media(
    hass: HomeAssistant, entity_id: str, media_content_id: str
) -> None:
    """Call media_player.play_media with the dashboard content type."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_CONTENT_TYPE: "dashboard",
            ATTR_MEDIA_CONTENT_ID: media_content_id,
        },
        blocking=True,
    )


async def test_dashboard_player_entities_from_cache(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test dashboard media players are created from the seeded cache."""
    setup_dashboards(music_assistant_client)
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "chromecast_kitchen_dashboard"), config_entry.entry_id
    )
    assert device
    assert device.manufacturer == "Music Assistant"
    assert device.model == "Dashboard display"
    assert device.name == "Kitchen Display"

    entry = entity_registry.async_get(KITCHEN_ENTITY_ID)
    assert entry
    assert entry.unique_id == "chromecast_kitchen_dashboard"

    # chromecast_kitchen has an active now_playing session for Test Player 1
    state = hass.states.get(KITCHEN_ENTITY_ID)
    assert state
    assert state.state == "playing"
    assert state.attributes["device_class"] == "tv"
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == "dashboard"
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == "now_playing/00:00:00:00:00:01"
    assert state.attributes[ATTR_MEDIA_TITLE] == "Now playing: Test Player 1"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.TURN_OFF
    )

    # fully_kiosk_hallway has no active session
    hallway_state = hass.states.get(HALLWAY_ENTITY_ID)
    assert hallway_state
    assert hallway_state.state == "idle"
    assert hallway_state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None

    # unmapped_player_display has an active session for a player unknown to
    # HA; the title falls back to the raw player id
    unmapped_state = hass.states.get(UNMAPPED_ENTITY_ID)
    assert unmapped_state
    assert unmapped_state.state == "playing"
    assert (
        unmapped_state.attributes[ATTR_MEDIA_CONTENT_ID]
        == "now_playing/not-exposed-player"
    )
    assert (
        unmapped_state.attributes[ATTR_MEDIA_TITLE] == "Now playing: not-exposed-player"
    )


async def test_dashboard_play_media_party(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media with the party dashboard type."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    await _play_media(hass, KITCHEN_ENTITY_ID, "party")

    assert music_assistant_client.send_command.call_args == call(
        "dashboard/show",
        dashboard_id="chromecast_kitchen",
        dashboard=DashboardType.PARTY,
        player_id=None,
        require_schema=39,
    )


async def test_dashboard_play_media_music_quiz(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media with the music_quiz dashboard type."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    await _play_media(hass, HALLWAY_ENTITY_ID, "music_quiz")

    assert music_assistant_client.send_command.call_args == call(
        "dashboard/show",
        dashboard_id="fully_kiosk_hallway",
        dashboard=DashboardType.MUSIC_QUIZ,
        player_id=None,
        require_schema=39,
    )


async def test_dashboard_play_media_now_playing(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media with a now_playing dashboard and player id."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    await _play_media(hass, HALLWAY_ENTITY_ID, "now_playing/00:00:00:00:00:02")

    assert music_assistant_client.send_command.call_args == call(
        "dashboard/show",
        dashboard_id="fully_kiosk_hallway",
        dashboard=DashboardType.NOW_PLAYING,
        player_id="00:00:00:00:00:02",
        require_schema=39,
    )


async def test_dashboard_play_media_wrong_content_type(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media rejects any media_content_type but dashboard."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    with pytest.raises(ServiceValidationError, match="media_content_type"):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: KITCHEN_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: "music",
                ATTR_MEDIA_CONTENT_ID: "party",
            },
            blocking=True,
        )


async def test_dashboard_play_media_unknown_type(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media rejects an unknown dashboard type."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    with pytest.raises(ServiceValidationError, match="Unknown dashboard"):
        await _play_media(hass, KITCHEN_ENTITY_ID, "not_a_dashboard")


async def test_dashboard_play_media_unsupported_type(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media rejects a type not in the display's supported_types."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # chromecast_kitchen only supports party and now_playing
    with pytest.raises(ServiceValidationError, match="does not support"):
        await _play_media(hass, KITCHEN_ENTITY_ID, "music_quiz")


async def test_dashboard_play_media_now_playing_missing_player(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media rejects now_playing without a player segment."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    with pytest.raises(ServiceValidationError, match="requires a player"):
        await _play_media(hass, HALLWAY_ENTITY_ID, "now_playing")


async def test_dashboard_play_media_now_playing_unknown_player(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media rejects an unknown player id."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    with pytest.raises(ServiceValidationError, match="Unknown or unexposed"):
        await _play_media(hass, HALLWAY_ENTITY_ID, "now_playing/does-not-exist")


async def test_dashboard_play_media_now_playing_unexposed_player(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test play_media rejects a player that is not exposed to HA."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    hidden_player = dataclasses.replace(
        music_assistant_client.players._players["00:00:00:00:00:01"],
        player_id="hidden-player",
        name="Hidden Player",
        expose_to_ha=False,
    )
    music_assistant_client.players._players["hidden-player"] = hidden_player

    with pytest.raises(ServiceValidationError, match="Unknown or unexposed"):
        await _play_media(hass, HALLWAY_ENTITY_ID, "now_playing/hidden-player")


async def test_dashboard_turn_off(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test turn_off hides the dashboard."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: KITCHEN_ENTITY_ID},
        blocking=True,
    )

    assert music_assistant_client.send_command.call_args == call(
        "dashboard/hide",
        dashboard_id="chromecast_kitchen",
        require_schema=39,
    )


async def test_dashboard_browse_media_root(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the root browse listing is filtered to the display's supported_types."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    client = await hass_ws_client(hass)

    # chromecast_kitchen supports party and now_playing, but not music_quiz
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": KITCHEN_ENTITY_ID,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    result = response["result"]
    assert [child["title"] for child in result["children"]] == [
        "Party",
        "Now playing",
    ]

    party_child = result["children"][0]
    assert party_child["media_content_id"] == "party"
    assert party_child["media_content_type"] == "dashboard"
    assert party_child["media_class"] == "app"
    assert party_child["can_play"] is True
    assert party_child["can_expand"] is False
    assert party_child["thumbnail"].startswith(
        f"/api/media_player_proxy/{KITCHEN_ENTITY_ID}/browse_media/dashboard/party?"
    )

    now_playing_child = result["children"][1]
    assert now_playing_child["media_content_id"] == "now_playing"
    assert now_playing_child["media_class"] == "directory"
    assert now_playing_child["can_play"] is False
    assert now_playing_child["can_expand"] is True
    assert now_playing_child["thumbnail"] is None

    # fully_kiosk_hallway supports party/now_playing/music_quiz (+ UNKNOWN,
    # which is always excluded)
    await client.send_json(
        {
            "id": 2,
            "type": "media_player/browse_media",
            "entity_id": HALLWAY_ENTITY_ID,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    hallway_children = response["result"]["children"]
    assert [child["title"] for child in hallway_children] == [
        "Party",
        "Music quiz",
        "Now playing",
    ]
    music_quiz_child = hallway_children[1]
    assert music_quiz_child["thumbnail"].startswith(
        f"/api/media_player_proxy/{HALLWAY_ENTITY_ID}/browse_media/dashboard/music_quiz?"
    )


async def test_dashboard_browse_media_now_playing_folder(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the now playing folder lists only players exposed to HA, sorted by name."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # add a player that is not exposed to HA; it must not show up
    hidden_player = dataclasses.replace(
        music_assistant_client.players._players["00:00:00:00:00:01"],
        player_id="hidden-player",
        name="Aaa Hidden Player",
        expose_to_ha=False,
    )
    music_assistant_client.players._players["hidden-player"] = hidden_player

    # give Test Player 1 an image so its browse thumbnail is populated
    art_url = "https://example.com/art.jpg"
    music_assistant_client.players._players[
        "00:00:00:00:00:01"
    ].current_media = PlayerMedia(uri="spotify://track/x", image_url=art_url)

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": HALLWAY_ENTITY_ID,
            "media_content_type": "dashboard",
            "media_content_id": "now_playing",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    result = response["result"]
    assert result["media_content_id"] == "now_playing"
    assert result["title"] == "Now playing"

    children = result["children"]
    assert [child["title"] for child in children] == [
        "My Super Test Player 2",
        "Test Group Player 1",
        "Test Player 1",
    ]
    for child in children:
        assert child["media_content_type"] == "dashboard"
        assert child["media_class"] == "app"
        assert child["can_play"] is True
        assert child["can_expand"] is False

    test_player_1_child = next(
        child for child in children if child["title"] == "Test Player 1"
    )
    assert test_player_1_child["media_content_id"] == "now_playing/00:00:00:00:00:01"
    assert test_player_1_child["thumbnail"] == art_url

    # players without current media get no thumbnail
    other_child = next(child for child in children if child["title"] != "Test Player 1")
    assert other_child["thumbnail"] is None


async def test_dashboard_async_get_browse_image(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test async_get_browse_image decodes the provider icon data URI and caches it."""
    setup_dashboards(music_assistant_client)
    _mock_provider_icon(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    entity = _get_dashboard_entity(hass, KITCHEN_ENTITY_ID)
    data, content_type = await entity.async_get_browse_image("dashboard", "party")
    assert data == PROVIDER_ICON_BYTES
    assert content_type == PROVIDER_ICON_CONTENT_TYPE

    # a second fetch for the same provider domain must not re-hit the server
    await entity.async_get_browse_image("dashboard", "party")
    icon_calls = [
        icon_call
        for icon_call in music_assistant_client.send_command.call_args_list
        if icon_call.args[:1] == ("providers/icon",)
    ]
    assert len(icon_calls) == 1


async def test_dashboard_async_get_browse_image_no_icon(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test async_get_browse_image returns (None, None) when the server has no icon."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    entity = _get_dashboard_entity(hass, KITCHEN_ENTITY_ID)
    assert await entity.async_get_browse_image("dashboard", "party") == (None, None)


async def test_dashboard_async_get_browse_image_rejects_unknown_content_id(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test async_get_browse_image rejects any id besides the two icon domains.

    This bounds the icon cache to the party/music_quiz keys it's sized for,
    and must reject before ever touching the cache or the server.
    """
    setup_dashboards(music_assistant_client)
    _mock_provider_icon(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    entity = _get_dashboard_entity(hass, KITCHEN_ENTITY_ID)
    assert await entity.async_get_browse_image(
        "dashboard", "now_playing/00:00:00:00:00:01"
    ) == (None, None)
    assert entity._provider_icon_cache == {}
    icon_calls = [
        icon_call
        for icon_call in music_assistant_client.send_command.call_args_list
        if icon_call.args[:1] == ("providers/icon",)
    ]
    assert not icon_calls


@pytest.mark.parametrize(
    "malformed_data_uri",
    [
        "not-a-data-uri",
        "data:image/svg+xml;base64,",
        "data:image/svg+xml;base64,not_base64!!",
    ],
)
async def test_dashboard_async_get_browse_image_malformed_icon(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    malformed_data_uri: str,
) -> None:
    """Test a malformed provider icon data URI is handled without raising."""
    setup_dashboards(music_assistant_client)

    async def send_command(command: str, **kwargs: Any) -> Any:
        if command == "providers/icon":
            return malformed_data_uri
        return None

    music_assistant_client.send_command = AsyncMock(side_effect=send_command)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    entity = _get_dashboard_entity(hass, KITCHEN_ENTITY_ID)
    assert await entity.async_get_browse_image("dashboard", "party") == (None, None)


async def test_dashboard_dynamic_add_and_unavailable(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test entities appear for a newly registered endpoint, and go unavailable."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    assert hass.states.get("media_player.new_display") is None

    music_assistant_client.dashboard._dashboards["new_display"] = DashboardDevice(
        dashboard_id="new_display",
        name="New Display",
        supported_types={DashboardType.PARTY},
    )
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARDS_UPDATED,
        data=_dashboards_event_data(music_assistant_client),
    )

    new_state = hass.states.get("media_player.new_display")
    assert new_state
    assert new_state.state == "idle"

    # the endpoint disappears from the cache (e.g. provider unloaded); the
    # entity stays but becomes unavailable
    del music_assistant_client.dashboard._dashboards["new_display"]
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARDS_UPDATED,
        data=_dashboards_event_data(music_assistant_client),
    )

    new_state = hass.states.get("media_player.new_display")
    assert new_state
    assert new_state.state == STATE_UNAVAILABLE

    kitchen_state = hass.states.get(KITCHEN_ENTITY_ID)
    assert kitchen_state
    assert kitchen_state.state != STATE_UNAVAILABLE


async def test_dashboard_session_mirroring(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test the entity mirrors a session starting, changing and ending."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    assert hass.states.get(HALLWAY_ENTITY_ID).state == "idle"

    # a party session starts
    music_assistant_client.dashboard._sessions["fully_kiosk_hallway"] = (
        DashboardSession(
            dashboard_id="fully_kiosk_hallway",
            name="Hallway Display",
            dashboard=DashboardType.PARTY,
        )
    )
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARD_SESSIONS_UPDATED,
        data=_sessions_event_data(music_assistant_client),
    )
    state = hass.states.get(HALLWAY_ENTITY_ID)
    assert state.state == "playing"
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == "party"
    assert state.attributes[ATTR_MEDIA_TITLE] == "Party"

    # a now_playing session takes over, for a specific player
    music_assistant_client.dashboard._sessions["fully_kiosk_hallway"] = (
        DashboardSession(
            dashboard_id="fully_kiosk_hallway",
            name="Hallway Display",
            dashboard=DashboardType.NOW_PLAYING,
            player_id="00:00:00:00:00:02",
        )
    )
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARD_SESSIONS_UPDATED,
        data=_sessions_event_data(music_assistant_client),
    )
    state = hass.states.get(HALLWAY_ENTITY_ID)
    assert state.state == "playing"
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == "now_playing/00:00:00:00:00:02"
    assert state.attributes[ATTR_MEDIA_TITLE] == "Now playing: My Super Test Player 2"

    # the session ends
    del music_assistant_client.dashboard._sessions["fully_kiosk_hallway"]
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARD_SESSIONS_UPDATED,
        data=_sessions_event_data(music_assistant_client),
    )
    state = hass.states.get(HALLWAY_ENTITY_ID)
    assert state.state == "idle"
    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) is None


async def test_dashboard_session_media_image_party_and_music_quiz(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test party/music_quiz sessions serve the provider icon, hashed by session type."""
    setup_dashboards(music_assistant_client)
    _mock_provider_icon(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    entity = _get_dashboard_entity(hass, HALLWAY_ENTITY_ID)
    assert entity.media_image_hash is None
    assert await entity.async_get_media_image() == (None, None)

    music_assistant_client.dashboard._sessions["fully_kiosk_hallway"] = (
        DashboardSession(
            dashboard_id="fully_kiosk_hallway",
            name="Hallway Display",
            dashboard=DashboardType.PARTY,
        )
    )
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARD_SESSIONS_UPDATED,
        data=_sessions_event_data(music_assistant_client),
    )
    party_hash = entity.media_image_hash
    assert party_hash is not None
    data, content_type = await entity.async_get_media_image()
    assert data == PROVIDER_ICON_BYTES
    assert content_type == PROVIDER_ICON_CONTENT_TYPE

    # the icon is served through the media proxy, not a direct media_image_url
    state = hass.states.get(HALLWAY_ENTITY_ID)
    assert state.attributes["entity_picture"].startswith(
        f"/api/media_player_proxy/{HALLWAY_ENTITY_ID}?"
    )

    music_assistant_client.dashboard._sessions["fully_kiosk_hallway"] = (
        DashboardSession(
            dashboard_id="fully_kiosk_hallway",
            name="Hallway Display",
            dashboard=DashboardType.MUSIC_QUIZ,
        )
    )
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARD_SESSIONS_UPDATED,
        data=_sessions_event_data(music_assistant_client),
    )
    assert entity.media_image_hash != party_hash

    del music_assistant_client.dashboard._sessions["fully_kiosk_hallway"]
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARD_SESSIONS_UPDATED,
        data=_sessions_event_data(music_assistant_client),
    )
    assert entity.media_image_hash is None
    assert await entity.async_get_media_image() == (None, None)


async def test_dashboard_now_playing_session_media_image(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test a now_playing session mirrors its player's artwork, refreshed on QUEUE_UPDATED."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # chromecast_kitchen's seeded now_playing session targets Test Player 1,
    # which starts without any media
    state = hass.states.get(KITCHEN_ENTITY_ID)
    assert state.attributes.get("entity_picture") is None

    entity = _get_dashboard_entity(hass, KITCHEN_ENTITY_ID)
    # not a party/music_quiz session, so no proxied provider icon either
    assert entity.media_image_hash is None

    art_url = "https://example.com/art.jpg"
    music_assistant_client.players._players[
        "00:00:00:00:00:01"
    ].current_media = PlayerMedia(uri="spotify://track/x", image_url=art_url)
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.QUEUE_UPDATED, "00:00:00:00:00:01"
    )

    state = hass.states.get(KITCHEN_ENTITY_ID)
    # a non-MA-hosted url is remotely accessible, so entity_picture is the raw url
    assert state.attributes["entity_picture"] == art_url


async def test_dashboard_now_playing_session_media_image_ma_hosted(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test MA-hosted now_playing artwork is proxied and actually fetched.

    Regression test: media_image_hash/async_get_media_image used to always
    return None for a now_playing session, so the base class's local-proxy
    fallback (which needs media_image_hash to build the proxy url, and
    fetches through async_get_media_image) never engaged and entity_picture
    silently disappeared for any MA-hosted artwork.
    """
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    art_url = f"{music_assistant_client.server_url}/imageproxy/track.jpg"
    music_assistant_client.players._players[
        "00:00:00:00:00:01"
    ].current_media = PlayerMedia(uri="spotify://track/x", image_url=art_url)
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.QUEUE_UPDATED, "00:00:00:00:00:01"
    )

    state = hass.states.get(KITCHEN_ENTITY_ID)
    entity_picture = state.attributes["entity_picture"]
    # MA-hosted artwork is not remotely accessible, so it's served through
    # the local media proxy rather than as a direct url
    assert entity_picture.startswith(f"/api/media_player_proxy/{KITCHEN_ENTITY_ID}?")

    aioclient_mock.get(
        art_url, content=b"artwork-bytes", headers={"Content-Type": "image/jpeg"}
    )
    client = await hass_client()
    response = await client.get(entity_picture)
    assert response.status == 200
    assert await response.read() == b"artwork-bytes"


async def test_dashboard_now_playing_session_media_image_player_updated(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test a now_playing session's artwork also refreshes on PLAYER_UPDATED."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    state = hass.states.get(KITCHEN_ENTITY_ID)
    assert state.attributes.get("entity_picture") is None

    art_url = "https://example.com/player-art.jpg"
    music_assistant_client.players._players[
        "00:00:00:00:00:01"
    ].current_media = PlayerMedia(uri="spotify://track/x", image_url=art_url)
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_UPDATED, "00:00:00:00:00:01"
    )

    state = hass.states.get(KITCHEN_ENTITY_ID)
    assert state.attributes["entity_picture"] == art_url


async def test_dashboard_now_playing_session_media_image_active_group_match(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test QUEUE_UPDATED for the session player's active_group also refreshes artwork.

    Mirrors MusicAssistantEntity.__on_mass_update's active_group matching, so
    artwork stays in sync when the session's player is joined into a group.
    """
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    music_assistant_client.players._players[
        "00:00:00:00:00:01"
    ].active_group = "group-1"

    art_url = "https://example.com/group-art.jpg"
    music_assistant_client.players._players[
        "00:00:00:00:00:01"
    ].current_media = PlayerMedia(uri="spotify://track/x", image_url=art_url)
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.QUEUE_UPDATED, "group-1"
    )

    state = hass.states.get(KITCHEN_ENTITY_ID)
    assert state.attributes["entity_picture"] == art_url


async def test_dashboard_session_transition_now_playing_remote_to_party(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test switching from a now_playing session with remote art to a party session.

    Regression test for _clear_media_image: without resetting
    media_image_remotely_accessible, entity_picture would incorrectly
    short-circuit to the (now None) media_image_url instead of falling
    through to the local proxy serving the party icon.
    """
    setup_dashboards(music_assistant_client)
    _mock_provider_icon(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    art_url = "https://example.com/remote-art.jpg"
    music_assistant_client.players._players[
        "00:00:00:00:00:01"
    ].current_media = PlayerMedia(uri="spotify://track/x", image_url=art_url)
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.QUEUE_UPDATED, "00:00:00:00:00:01"
    )
    state = hass.states.get(KITCHEN_ENTITY_ID)
    assert state.attributes["entity_picture"] == art_url

    music_assistant_client.dashboard._sessions["chromecast_kitchen"] = DashboardSession(
        dashboard_id="chromecast_kitchen",
        name="Kitchen Display",
        dashboard=DashboardType.PARTY,
    )
    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.DASHBOARD_SESSIONS_UPDATED,
        data=_sessions_event_data(music_assistant_client),
    )

    state = hass.states.get(KITCHEN_ENTITY_ID)
    assert state.attributes["entity_picture"].startswith(
        f"/api/media_player_proxy/{KITCHEN_ENTITY_ID}?"
    )


async def test_dashboard_browse_media_unknown_content_id(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing an id that isn't a known dashboard or the now_playing folder."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": KITCHEN_ENTITY_ID,
            "media_content_type": "dashboard",
            "media_content_id": "not_a_real_id",
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unknown_error"


async def test_dashboard_browse_media_display_gone_from_cache(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing a display that dropped out of the dashboard cache.

    The browse websocket command fetches the entity directly and does not
    filter on availability, so this can be hit on a still-registered but
    unavailable display.
    """
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    client = await hass_ws_client(hass)

    del music_assistant_client.dashboard._dashboards["chromecast_kitchen"]

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": KITCHEN_ENTITY_ID,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unknown_error"


async def test_dashboard_browse_media_now_playing_folder_unsupported(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing the now_playing folder directly on a display that lacks it."""
    setup_dashboards(music_assistant_client)
    music_assistant_client.dashboard._dashboards["party_only_display"] = (
        DashboardDevice(
            dashboard_id="party_only_display",
            name="Party Only Display",
            supported_types={DashboardType.PARTY},
        )
    )
    await setup_integration_from_fixtures(hass, music_assistant_client)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.party_only_display",
            "media_content_type": "dashboard",
            "media_content_id": "now_playing",
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unknown_error"


async def test_dashboard_media_player_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test dashboard display media player entities against a snapshot."""
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(
        hass, entity_registry, snapshot, Platform.MEDIA_PLAYER
    )


async def test_platform_entity_service_rejects_display(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test a player-only platform entity service fails cleanly on a display.

    These services (play_media, play_announcement, transfer_queue,
    get_queue) are registered for every music_assistant media_player
    entity; a display doesn't implement them and must be rejected up
    front, not crash with an AttributeError.
    """
    setup_dashboards(music_assistant_client)
    await setup_integration_from_fixtures(hass, music_assistant_client)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ANNOUNCEMENT,
            {
                ATTR_ENTITY_ID: KITCHEN_ENTITY_ID,
                ATTR_URL: "http://blah.com/announcement.mp3",
            },
            blocking=True,
        )


async def test_platform_entity_service_skips_display_indirect_target(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test a display targeted indirectly is skipped rather than rejected.

    Naming the display's entity directly raises (see
    test_platform_entity_service_rejects_display); targeting it indirectly,
    e.g. through a device or area that also holds a supported entity, must
    instead silently skip it while still servicing the supported one.
    """
    setup_dashboards(music_assistant_client)
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)

    player_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "00:00:00:00:00:01"), config_entry.entry_id
    )
    display_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "chromecast_kitchen_dashboard"), config_entry.entry_id
    )
    assert player_device
    assert display_device

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_ANNOUNCEMENT,
        {
            ATTR_DEVICE_ID: [player_device.id, display_device.id],
            ATTR_URL: "http://blah.com/announcement.mp3",
        },
        blocking=True,
    )

    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/play_announcement",
        require_schema=None,
        player_id="00:00:00:00:00:01",
        url="http://blah.com/announcement.mp3",
        pre_announce=None,
        volume_level=None,
        pre_announce_url=None,
        message=None,
        tts_engine=None,
    )
