"""Test Music Assistant dashboard display media player entities."""

import dataclasses
from unittest.mock import MagicMock, call

from music_assistant_models.dashboard import DashboardDevice, DashboardSession
from music_assistant_models.enums import DashboardType, EventType
import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    setup_dashboards,
    setup_integration_from_fixtures,
    trigger_subscription_callback,
)

from tests.typing import WebSocketGenerator

KITCHEN_ENTITY_ID = "media_player.kitchen_display"
HALLWAY_ENTITY_ID = "media_player.hallway_display"
UNMAPPED_ENTITY_ID = "media_player.unmapped_player_display"


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
        (DOMAIN, "chromecast_kitchen"), config_entry.entry_id
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

    with pytest.raises(ServiceValidationError, match="player"):
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

    now_playing_child = result["children"][1]
    assert now_playing_child["media_content_id"] == "now_playing"
    assert now_playing_child["media_class"] == "directory"
    assert now_playing_child["can_play"] is False
    assert now_playing_child["can_expand"] is True

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
    assert [child["title"] for child in response["result"]["children"]] == [
        "Party",
        "Music quiz",
        "Now playing",
    ]


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
        hass, music_assistant_client, EventType.DASHBOARDS_UPDATED
    )

    new_state = hass.states.get("media_player.new_display")
    assert new_state
    assert new_state.state == "idle"

    # the endpoint disappears from the cache (e.g. provider unloaded); the
    # entity stays but becomes unavailable
    del music_assistant_client.dashboard._dashboards["new_display"]
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.DASHBOARDS_UPDATED
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
        hass, music_assistant_client, EventType.DASHBOARD_SESSIONS_UPDATED
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
        hass, music_assistant_client, EventType.DASHBOARD_SESSIONS_UPDATED
    )
    state = hass.states.get(HALLWAY_ENTITY_ID)
    assert state.state == "playing"
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == "now_playing/00:00:00:00:00:02"
    assert state.attributes[ATTR_MEDIA_TITLE] == "Now playing: My Super Test Player 2"

    # the session ends
    del music_assistant_client.dashboard._sessions["fully_kiosk_hallway"]
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.DASHBOARD_SESSIONS_UPDATED
    )
    state = hass.states.get(HALLWAY_ENTITY_ID)
    assert state.state == "idle"
    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) is None
