"""Tests for the Yoto media player platform."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from yoto_api import Chapter, YotoError

from homeassistant.components.media_player import (
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_VOLUME_SET,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator

ENTITY_ID = "media_player.nursery_yoto"

pytestmark = pytest.mark.usefixtures("setup_credentials")


@pytest.mark.usefixtures("mock_token_hex", "mock_yoto_client")
async def test_entity_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Snapshot the media player entity state."""
    freezer.move_to("2026-05-08T12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_MEDIA_PLAY, "resume"),
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_STOP, "stop"),
        (SERVICE_MEDIA_NEXT_TRACK, "next_track"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous_track"),
    ],
)
async def test_playback_commands(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Playback service calls reach the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    getattr(mock_yoto_client, method).assert_called_once_with("player-test")


async def test_set_volume(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Volume is forwarded as an integer 0-100."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )

    mock_yoto_client.set_volume.assert_called_once_with("player-test", 50)


async def test_seek(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Seek delegates to the client with the integer position."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_SEEK_POSITION: 30},
        blocking=True,
    )

    mock_yoto_client.seek.assert_called_once_with("player-test", 30)


async def test_state_unavailable_when_offline(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When the player reports offline the entity is unavailable."""
    player = next(iter(mock_yoto_client.players.values()))
    player.status.is_online = False

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_no_card_metadata_when_card_id_missing(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Card metadata properties return None when no card is active."""
    player = next(iter(mock_yoto_client.players.values()))
    player.last_event.card_id = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert "media_album_name" not in state.attributes
    assert "media_artist" not in state.attributes
    assert "entity_picture" not in state.attributes


async def test_state_idle_before_first_event(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A freshly-online player with no playback event yet reports IDLE."""
    player = next(iter(mock_yoto_client.players.values()))
    player.last_event.playback_status = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.IDLE


@pytest.mark.parametrize(
    ("media_content_id", "expected_call"),
    [
        (
            "yoto://card-test",
            {"chapter_key": None, "track_key": None, "seconds_in": None},
        ),
        (
            "yoto://card-test/01",
            {"chapter_key": "01", "track_key": "01-INT", "seconds_in": 0},
        ),
        (
            "yoto://card-test/01/01-INT",
            {"chapter_key": "01", "track_key": "01-INT", "seconds_in": 0},
        ),
    ],
)
async def test_play_media(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    media_content_id: str,
    expected_call: dict[str, Any],
) -> None:
    """play_media routes a yoto:// URI to the right play_card call."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": media_content_id,
        },
        blocking=True,
    )

    mock_yoto_client.play_card.assert_called_once_with(
        "player-test", "card-test", **expected_call
    )


@pytest.mark.parametrize(
    "media_content_id",
    ["spotify:track:abc", "yoto://"],
)
async def test_play_media_invalid_uri_raises(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    media_content_id: str,
) -> None:
    """A media_id that isn't a complete yoto:// URI is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "media_content_type": "music",
                "media_content_id": media_content_id,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "media_content_id",
    [
        pytest.param("yoto://does-not-exist", id="unknown_card"),
        pytest.param("yoto://card-test/does-not-exist", id="unknown_chapter"),
    ],
)
async def test_play_media_unknown_target_raises(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    media_content_id: str,
) -> None:
    """A yoto:// URI pointing at unknown content is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "media_content_type": "music",
                "media_content_id": media_content_id,
            },
            blocking=True,
        )

    mock_yoto_client.play_card.assert_not_called()


async def test_browse_media_root_lists_cards(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing without a content id lists every library card."""
    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {"id": 1, "type": "media_player/browse_media", "entity_id": ENTITY_ID}
    )
    response = await client.receive_json()

    assert response["success"]
    children = response["result"]["children"]
    assert len(children) == 1
    assert children[0]["title"] == "Outer Space"
    assert children[0]["media_content_id"] == "yoto://card-test"
    assert children[0]["can_play"] is True
    assert children[0]["can_expand"] is True


async def test_browse_media_card_shows_chapters(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a multi-chapter card shows its chapters."""
    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "album",
            "media_content_id": "yoto://card-test",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    children = response["result"]["children"]
    assert [c["title"] for c in children] == ["Introduction", "Planets"]
    assert children[0]["media_content_id"] == "yoto://card-test/01"
    # "Introduction" has 2 tracks → expandable; "Planets" has 1 track → leaf.
    assert children[0]["can_expand"] is True
    assert children[1]["can_expand"] is False


async def test_browse_media_single_chapter_card_collapses_to_tracks(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A card with a single chapter shows its tracks directly."""
    card = mock_yoto_client.library["card-test"]
    card.chapters = {"01": card.chapters["01"]}

    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "album",
            "media_content_id": "yoto://card-test",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    children = response["result"]["children"]
    assert [c["title"] for c in children] == ["Welcome", "The Story Begins"]
    assert children[0]["media_content_id"] == "yoto://card-test/01/01-INT"


async def test_browse_media_chapter_shows_tracks(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a chapter lists its tracks."""
    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "playlist",
            "media_content_id": "yoto://card-test/01",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    children = response["result"]["children"]
    assert [c["title"] for c in children] == ["Welcome", "The Story Begins"]
    assert children[0]["media_content_id"] == "yoto://card-test/01/01-INT"


async def test_browse_media_fetches_card_detail_lazily(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a card without loaded chapters triggers update_card_detail."""
    card = mock_yoto_client.library["card-test"]
    card.chapters = None

    async def _populate(card_id: str) -> None:
        card.chapters = {"01": Chapter(key="01", title="Intro", tracks={})}

    mock_yoto_client.update_card_detail.side_effect = _populate

    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "album",
            "media_content_id": "yoto://card-test",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    mock_yoto_client.update_card_detail.assert_called_once_with("card-test")


async def test_browse_media_unknown_card_raises(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a card that's not in the library returns a browse error."""
    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "album",
            "media_content_id": "yoto://does-not-exist",
        }
    )
    response = await client.receive_json()
    assert response["success"] is False


async def test_browse_media_unknown_chapter_raises(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a chapter that's not in the card returns a browse error."""
    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "playlist",
            "media_content_id": "yoto://card-test/does-not-exist",
        }
    )
    response = await client.receive_json()
    assert response["success"] is False


async def test_browse_media_card_detail_failure_raises(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A failure fetching card chapters bubbles up as a browse error."""
    card = mock_yoto_client.library["card-test"]
    card.chapters = None
    mock_yoto_client.update_card_detail.side_effect = YotoError("offline")

    await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "album",
            "media_content_id": "yoto://card-test",
        }
    )
    response = await client.receive_json()
    assert response["success"] is False


@pytest.mark.parametrize(
    ("client_method", "service", "service_data"),
    [
        pytest.param("pause", SERVICE_MEDIA_PAUSE, {}, id="playback"),
        pytest.param(
            "play_card",
            SERVICE_PLAY_MEDIA,
            {"media_content_type": "music", "media_content_id": "yoto://card-test"},
            id="play_media",
        ),
    ],
)
async def test_command_error_raises(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    client_method: str,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Yoto command failures surface as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    getattr(mock_yoto_client, client_method).side_effect = YotoError("nope")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )
