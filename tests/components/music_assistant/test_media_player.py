"""Test Music Assistant media player entities."""

from unittest.mock import MagicMock, call

from music_assistant_models.constants import PLAYER_CONTROL_NONE
from music_assistant_models.enums import (
    EventType,
    MediaType,
    PlayerFeature,
    QueueOption,
)
from music_assistant_models.errors import UserNotFoundError
from music_assistant_models.media_items import Track
from music_assistant_models.player import PlayerMedia
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths
import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    MediaPlayerEntityFeature,
)
from homeassistant.components.music_assistant.const import (
    ATTR_ALBUM,
    ATTR_ANNOUNCE_VOLUME,
    ATTR_ARTIST,
    ATTR_AUTO_PLAY,
    ATTR_MEDIA_ID,
    ATTR_MEDIA_TYPE,
    ATTR_MESSAGE,
    ATTR_PRE_ANNOUNCE_URL,
    ATTR_RADIO_MODE,
    ATTR_SOURCE_PLAYER,
    ATTR_TTS_ENTITY_ID,
    ATTR_URL,
    ATTR_USE_PRE_ANNOUNCE,
    ATTR_USERNAME,
    DOMAIN,
)
from homeassistant.components.music_assistant.media_player import MusicAssistantPlayer
from homeassistant.components.music_assistant.services import (
    SERVICE_GET_QUEUE,
    SERVICE_PLAY_ANNOUNCEMENT,
    SERVICE_PLAY_MEDIA_ADVANCED,
    SERVICE_TRANSFER_QUEUE,
)
from homeassistant.components.tts import DATA_TTS_MANAGER
from homeassistant.config_entries import ConfigFlow, HomeAssistantError
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import (
    create_players_from_fixture,
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)

from tests.common import AsyncMock, MockUser, mock_config_flow, mock_platform
from tests.components.tts.common import (
    DEFAULT_LANG,
    MockTTSEntity,
    mock_config_entry_setup,
)

MOCK_TRACK = Track(
    item_id="1",
    provider="library",
    name="Test Track",
    provider_mappings={},
)
MOCK_TTS_ENTITY_ID = "tts.test"
MOCK_SECOND_TTS_ENTITY_ID = "tts.second"


class MockTTSConfigFlow(ConfigFlow):
    """Config flow for the mock text-to-speech integration."""


class MockSecondTTSEntity(MockTTSEntity):
    """Second mock text-to-speech entity."""

    _attr_name = "Second"


@pytest.fixture(name="tts_entities")
async def tts_entities_fixture(hass: HomeAssistant) -> None:
    """Set up two text-to-speech entities, of which the first is the default engine."""
    assert await async_setup_component(hass, "media_source", {})
    for test_domain, tts_entity in (
        ("test", MockTTSEntity(DEFAULT_LANG)),
        ("test2", MockSecondTTSEntity(DEFAULT_LANG)),
    ):
        mock_platform(hass, f"{test_domain}.config_flow")
        with mock_config_flow(test_domain, MockTTSConfigFlow):
            await mock_config_entry_setup(hass, tts_entity, test_domain=test_domain)


@pytest.mark.parametrize(
    ("mass_icon", "mdi_icon"),
    [
        pytest.param("speaker", "mdi:speaker", id="speaker"),
        pytest.param("speakers", "mdi:speaker-multiple", id="speakers"),
        pytest.param("tv", "mdi:television", id="tv"),
        pytest.param("smartphone", "mdi:cellphone", id="smartphone"),
        pytest.param("google-nest", "mdi:speaker", id="fallback"),
        pytest.param("mdi-speaker", "mdi:speaker", id="legacy-mdi-dash"),
        pytest.param("mdi:speaker", "mdi:speaker", id="legacy-mdi-colon"),
    ],
)
def test_player_icon(
    music_assistant_client: MagicMock, mass_icon: str, mdi_icon: str
) -> None:
    """Test Music Assistant player icon mapping."""
    player = create_players_from_fixture()[0]
    player.icon = mass_icon
    music_assistant_client.players._players[player.player_id] = player

    entity = MusicAssistantPlayer(music_assistant_client, player.player_id)

    assert entity.icon == mdi_icon


async def test_media_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test media player."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(
        hass, entity_registry, snapshot, Platform.MEDIA_PLAYER
    )


async def test_media_player_basic_actions(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity basic actions (play/stop/pause etc.)."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    for action, cmd in (
        (SERVICE_MEDIA_PLAY, "play"),
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_STOP, "stop"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous"),
        (SERVICE_MEDIA_NEXT_TRACK, "next"),
        (SERVICE_VOLUME_UP, "volume_up"),
        (SERVICE_VOLUME_DOWN, "volume_down"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            action,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

        assert music_assistant_client.send_command.call_count == 1
        assert music_assistant_client.send_command.call_args == call(
            f"players/cmd/{cmd}", player_id=mass_player_id
        )
        music_assistant_client.send_command.reset_mock()


async def test_media_player_seek_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity seek action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_seek",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_SEEK_POSITION: 100,
        },
        blocking=True,
    )

    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/seek", player_id=mass_player_id, position=100
    )


async def test_media_player_volume_set_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity volume_set action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/volume_set", player_id=mass_player_id, volume_level=50
    )


async def test_media_player_volume_mute_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity volume_mute action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/volume_mute", player_id=mass_player_id, muted=True
    )


async def test_media_player_turn_on_off_actions(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity turn_on/turn_off actions."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    for action, pwr in (
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            action,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
        assert music_assistant_client.send_command.call_count == 1
        assert music_assistant_client.send_command.call_args == call(
            "players/cmd/power", player_id=mass_player_id, powered=pwr
        )
        music_assistant_client.send_command.reset_mock()


async def test_media_player_shuffle_set_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity shuffle_set action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_SHUFFLE: True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/shuffle", queue_id=mass_player_id, shuffle_enabled=True
    )


async def test_media_player_repeat_set_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity repeat_set action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_REPEAT: "one",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/repeat", queue_id=mass_player_id, repeat_mode="one"
    )


async def test_media_player_join_players_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity join_players action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_GROUP_MEMBERS: ["media_player.my_super_test_player_2"],
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/group_many",
        target_player=mass_player_id,
        child_player_ids=["00:00:00:00:00:02"],
    )
    # test again with invalid source player
    music_assistant_client.send_command.reset_mock()
    with pytest.raises(
        HomeAssistantError, match="Entity media_player.blah_blah not found"
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_GROUP_MEMBERS: ["media_player.blah_blah"],
            },
            blocking=True,
        )


async def test_media_player_unjoin_player_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity unjoin player action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/ungroup", player_id=mass_player_id
    )


async def test_media_player_clear_playlist_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity clear_playlist action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_CLEAR_PLAYLIST,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/clear", queue_id=mass_player_id
    )


async def test_media_player_play_media_action_legacy(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player (advanced) play_media action.

    Legacy test for servers with API schema < 33
    """
    music_assistant_client.server_info.schema_version = 1

    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state

    # test simple play_media call with URI as media_id and no media type
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=False,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test simple play_media call with URI and enqueue specified
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
            ATTR_MEDIA_ENQUEUE: "add",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=QueueOption.ADD,
        radio_mode=False,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test basic play_media call with URL and radio mode specified
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
            ATTR_RADIO_MODE: True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=True,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test play_media call with media id and media type specified
    music_assistant_client.send_command.reset_mock()
    music_assistant_client.music.get_item = AsyncMock(return_value=MOCK_TRACK)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "1",
            ATTR_MEDIA_TYPE: "track",
        },
        blocking=True,
    )
    assert music_assistant_client.music.get_item.call_count == 1
    assert music_assistant_client.music.get_item.call_args == call(
        MediaType.TRACK, "1", "library"
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=[MOCK_TRACK.uri],
        option=None,
        radio_mode=False,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test play_media call by name
    music_assistant_client.send_command.reset_mock()
    music_assistant_client.music.get_item_by_name = AsyncMock(return_value=MOCK_TRACK)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "test",
            ATTR_ARTIST: "artist",
            ATTR_ALBUM: "album",
        },
        blocking=True,
    )
    assert music_assistant_client.music.get_item_by_name.call_count == 1
    assert music_assistant_client.music.get_item_by_name.call_args == call(
        name="test",
        artist="artist",
        album="album",
        media_type=None,
        user=None,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=[MOCK_TRACK.uri],
        option=None,
        radio_mode=False,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test with username
    # valid name
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
            ATTR_MEDIA_ENQUEUE: "add",
            ATTR_USERNAME: "user_user",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=QueueOption.ADD,
        radio_mode=False,
        start_item=None,
        sort_by=None,
        username="user_user",
    )


async def test_media_player_play_media_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player (advanced) play_media action.

    Test for servers with API schema >= 33
    """
    music_assistant_client.server_info.schema_version = 33

    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state

    # For the following test, make verify item uri indicate a valid uri
    music_assistant_client.music.verify_item_uri = AsyncMock(return_value=True)

    # test simple play_media call with URI as media_id and no media type
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=False,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test simple play_media call with URI and enqueue specified
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
            ATTR_MEDIA_ENQUEUE: "add",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=QueueOption.ADD,
        radio_mode=False,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test basic play_media call with URL and radio mode specified
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
            ATTR_RADIO_MODE: True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=True,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test play_media call with media id and media type specified
    ## numeric media id with media_type must verify as library item
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "1",
            ATTR_MEDIA_TYPE: "audiobook",
            ATTR_MEDIA_ENQUEUE: "add",
            ATTR_USERNAME: "user_user",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["library://audiobook/1"],
        option=QueueOption.ADD,
        radio_mode=False,
        start_item=None,
        sort_by=None,
        username="user_user",
    )

    # test play_media call by name as fallback if item uri is invalid
    music_assistant_client.music.verify_item_uri = AsyncMock(return_value=False)

    music_assistant_client.send_command.reset_mock()
    music_assistant_client.music.get_item_by_name = AsyncMock(return_value=MOCK_TRACK)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "test",
            ATTR_ARTIST: "artist",
            ATTR_ALBUM: "album",
        },
        blocking=True,
    )
    assert music_assistant_client.music.get_item_by_name.call_count == 1
    assert music_assistant_client.music.get_item_by_name.call_args == call(
        name="test",
        artist="artist",
        album="album",
        media_type=None,
        user=None,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=[MOCK_TRACK.uri],
        option=None,
        radio_mode=False,
        start_item=None,
        username=None,
        sort_by=None,
    )

    # test with username and valid item uris
    music_assistant_client.music.verify_item_uri = AsyncMock(return_value=True)
    # valid name
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
            ATTR_MEDIA_ENQUEUE: "add",
            ATTR_USERNAME: "user_user",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=QueueOption.ADD,
        radio_mode=False,
        start_item=None,
        sort_by=None,
        username="user_user",
    )


async def test_media_player_play_media_default_user(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that play media defaults to the calling Home Assistant user.

    The calling user is forwarded as a soft (required=False) provider-link user
    reference; the server resolves it to a Music Assistant user by provider link
    (or plays as the default account).
    """
    music_assistant_client.server_info.schema_version = 44
    music_assistant_client.music.verify_item_uri = AsyncMock(return_value=True)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"

    user = MockUser(is_owner=True).add_to_hass(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
        },
        blocking=True,
        context=Context(user_id=user.id),
    )
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=False,
        start_item=None,
        sort_by=None,
        user={"provider": "homeassistant", "user_id": user.id, "required": False},
    )


async def test_media_player_play_media_default_user_older_server(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that older servers (no provider-link support) simply do not impersonate."""
    # the provider-link user reference is only sent to schema >= 44 servers; being
    # soft (required=False), it gracefully degrades to no impersonation at all
    music_assistant_client.server_info.schema_version = 35
    music_assistant_client.music.verify_item_uri = AsyncMock(return_value=True)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"

    user = MockUser(is_owner=True).add_to_hass(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
        },
        blocking=True,
        context=Context(user_id=user.id),
    )
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=False,
        start_item=None,
        sort_by=None,
    )


async def test_media_player_play_media_explicit_user_override(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that an explicit username takes precedence over the calling user."""
    music_assistant_client.server_info.schema_version = 44
    music_assistant_client.music.verify_item_uri = AsyncMock(return_value=True)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"

    user = MockUser(is_owner=True).add_to_hass(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_ID: "spotify://track/1234",
            ATTR_USERNAME: "user_admin",
        },
        blocking=True,
        context=Context(user_id=user.id),
    )
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=False,
        start_item=None,
        sort_by=None,
        user="user_admin",
    )


async def test_media_player_play_media_unknown_username(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that a username the server does not know raises a translated error."""
    music_assistant_client.server_info.schema_version = 44
    music_assistant_client.music.verify_item_uri = AsyncMock(
        side_effect=UserNotFoundError(
            "A user with user id or name nobody is not available."
        )
    )
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA_ADVANCED,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MEDIA_ID: "spotify://track/1234",
                ATTR_USERNAME: "nobody",
            },
            blocking=True,
        )
    assert err.value.translation_key == "invalid_username"
    assert err.value.translation_placeholders == {"username": "nobody"}


async def test_media_player_play_media_user_not_found_without_username(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that a UserNotFoundError without an explicit username is not mislabeled."""
    music_assistant_client.server_info.schema_version = 44
    music_assistant_client.music.verify_item_uri = AsyncMock(
        side_effect=UserNotFoundError(
            "A user with user id or name nobody is not available."
        )
    )
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA_ADVANCED,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MEDIA_ID: "spotify://track/1234",
            },
            blocking=True,
        )
    assert not isinstance(err.value, ServiceValidationError)


async def test_media_player_standard_play_media_default_user(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that the standard play_media action also defaults to the calling user."""
    music_assistant_client.server_info.schema_version = 44
    music_assistant_client.music.verify_item_uri = AsyncMock(return_value=True)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"

    user = MockUser(is_owner=True).add_to_hass(hass)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_CONTENT_ID: "spotify://track/1234",
            ATTR_MEDIA_CONTENT_TYPE: "music",
        },
        blocking=True,
        context=Context(user_id=user.id),
    )
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/play_media",
        queue_id=mass_player_id,
        media=["spotify://track/1234"],
        option=None,
        radio_mode=False,
        start_item=None,
        sort_by=None,
        user={"provider": "homeassistant", "user_id": user.id, "required": False},
    )


async def test_media_player_play_announcement_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player play_announcement action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_ANNOUNCEMENT,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_URL: "http://blah.com/announcement.mp3",
            ATTR_USE_PRE_ANNOUNCE: True,
            ATTR_PRE_ANNOUNCE_URL: "http://blah.com/chime.mp3",
            ATTR_ANNOUNCE_VOLUME: 50,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/play_announcement",
        require_schema=None,
        player_id=mass_player_id,
        url="http://blah.com/announcement.mp3",
        pre_announce=True,
        volume_level=50,
        pre_announce_url="http://blah.com/chime.mp3",
        message=None,
        tts_engine=None,
    )


@pytest.mark.parametrize(
    "tts_entity_id",
    [MOCK_TTS_ENTITY_ID, MOCK_SECOND_TTS_ENTITY_ID],
    ids=["default tts entity", "non-default tts entity"],
)
@pytest.mark.usefixtures("mock_tts_cache_dir", "tts_entities")
async def test_media_player_play_announcement_action_with_message(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    tts_entity_id: str,
) -> None:
    """Test media_player play_announcement action speaks a message with the given entity."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_ANNOUNCEMENT,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MESSAGE: "Dinner is ready!",
            ATTR_TTS_ENTITY_ID: tts_entity_id,
            ATTR_USE_PRE_ANNOUNCE: True,
            ATTR_ANNOUNCE_VOLUME: 50,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    announcement_url = music_assistant_client.send_command.call_args.kwargs["url"]
    assert announcement_url.startswith("http://example.local:8123/api/tts_proxy/")
    stream = hass.data[DATA_TTS_MANAGER].token_to_stream[
        announcement_url.rsplit("/", 1)[-1]
    ]
    assert stream.engine == tts_entity_id
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/play_announcement",
        require_schema=None,
        player_id=mass_player_id,
        url=announcement_url,
        pre_announce=True,
        volume_level=50,
        pre_announce_url=None,
        message=None,
        tts_engine=None,
    )


@pytest.mark.parametrize(
    "announcement_data",
    [
        {},
        {
            ATTR_URL: "http://blah.com/announcement.mp3",
            ATTR_MESSAGE: "Dinner is ready!",
            ATTR_TTS_ENTITY_ID: MOCK_TTS_ENTITY_ID,
        },
        {ATTR_MESSAGE: "Dinner is ready!"},
        {
            ATTR_URL: "http://blah.com/announcement.mp3",
            ATTR_TTS_ENTITY_ID: MOCK_TTS_ENTITY_ID,
        },
        {
            ATTR_MESSAGE: "Dinner is ready!",
            ATTR_TTS_ENTITY_ID: "media_player.test_player_2",
        },
    ],
    ids=[
        "neither url nor message",
        "both url and message",
        "message without tts entity",
        "tts entity without message",
        "entity outside the tts domain",
    ],
)
async def test_media_player_play_announcement_action_invalid_input(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    announcement_data: dict[str, str],
) -> None:
    """Test play_announcement action requires either a url or a message with an entity."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ANNOUNCEMENT,
            {
                ATTR_ENTITY_ID: "media_player.test_player_1",
                **announcement_data,
            },
            blocking=True,
        )
    assert music_assistant_client.send_command.call_count == 0


@pytest.mark.parametrize(
    "tts_entity_id",
    ["tts.does_not_exist", MOCK_TTS_ENTITY_ID],
    ids=["unknown tts entity", "unavailable tts entity"],
)
async def test_media_player_play_announcement_action_unusable_tts_entity(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    tts_entity_id: str,
) -> None:
    """Test play_announcement action reports a text-to-speech entity it cannot use."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    hass.states.async_set(MOCK_TTS_ENTITY_ID, STATE_UNAVAILABLE)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_ANNOUNCEMENT,
            {
                ATTR_ENTITY_ID: "media_player.test_player_1",
                ATTR_MESSAGE: "Dinner is ready!",
                ATTR_TTS_ENTITY_ID: tts_entity_id,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "tts_entity_not_available"
    assert music_assistant_client.send_command.call_count == 0


async def test_media_player_transfer_queue_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player transfer_queu action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TRANSFER_QUEUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_SOURCE_PLAYER: "media_player.my_super_test_player_2",
            ATTR_AUTO_PLAY: True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/transfer",
        source_queue_id="00:00:00:00:00:02",
        target_queue_id="00:00:00:00:00:01",
        auto_play=True,
        require_schema=25,
    )
    # test again with invalid source player
    music_assistant_client.send_command.reset_mock()
    with pytest.raises(HomeAssistantError, match="Source player not available."):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TRANSFER_QUEUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_SOURCE_PLAYER: "media_player.blah_blah",
            },
            blocking=True,
        )
    # test again with no source player specified (which picks first playing playerqueue)
    music_assistant_client.send_command.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TRANSFER_QUEUE,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/transfer",
        source_queue_id="test_group_player_1",
        target_queue_id="00:00:00:00:00:01",
        auto_play=None,
        require_schema=25,
    )


async def test_media_player_get_queue_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test media_player get_queue action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_group_player_1"
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
        return_response=True,
    )
    # no call is made, this info comes from the cached queue data
    assert music_assistant_client.send_command.call_count == 0
    assert response == snapshot(exclude=paths(f"{entity_id}.elapsed_time"))


async def test_media_player_select_source_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity select source action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_INPUT_SOURCE: "Line-In",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/select_source", player_id=mass_player_id, source="linein"
    )


async def test_media_player_select_sound_mode_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity select sound mode action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_SOUND_MODE: "munich_translation",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/select_sound_mode",
        player_id=mass_player_id,
        sound_mode="munich_id",
    )


async def test_passive_sound_mode_ignored(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Verify, that a passive sound mode is ignored."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    passive_sound_mode_translation_key = "passive_sound_mode_translation"
    active_sound_mode_translation_key = "munich_translation"
    state = hass.states.get(entity_id)
    assert state
    sound_modes = state.attributes["sound_mode_list"]
    assert active_sound_mode_translation_key in sound_modes
    assert passive_sound_mode_translation_key not in sound_modes


async def test_media_player_supported_features(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test if media_player entity supported features are cortrectly (re)mapped."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    expected_features = (
        MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.MEDIA_ENQUEUE
        | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.GROUPING
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SEARCH_MEDIA
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    assert state.attributes["supported_features"] == expected_features
    # remove power control capability from player, trigger subscription callback
    # and check if the supported features got updated
    music_assistant_client.players._players[
        mass_player_id
    ].power_control = PLAYER_CONTROL_NONE
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_CONFIG_UPDATED, mass_player_id
    )
    expected_features &= ~MediaPlayerEntityFeature.TURN_ON
    expected_features &= ~MediaPlayerEntityFeature.TURN_OFF
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] == expected_features

    # remove volume control capability from player, trigger subscription callback
    # and check if the supported features got updated
    music_assistant_client.players._players[
        mass_player_id
    ].volume_control = PLAYER_CONTROL_NONE
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_CONFIG_UPDATED, mass_player_id
    )
    expected_features &= ~MediaPlayerEntityFeature.VOLUME_SET
    expected_features &= ~MediaPlayerEntityFeature.VOLUME_STEP
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] == expected_features

    # remove mute control capability from player, trigger subscription callback
    # and check if the supported features got updated
    music_assistant_client.players._players[
        mass_player_id
    ].mute_control = PLAYER_CONTROL_NONE
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_CONFIG_UPDATED, mass_player_id
    )
    expected_features &= ~MediaPlayerEntityFeature.VOLUME_MUTE
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] == expected_features

    # remove grouping capability from player, trigger subscription callback
    # and check if the supported features got updated
    music_assistant_client.players._players[mass_player_id].supported_features.remove(
        PlayerFeature.SET_MEMBERS
    )
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_CONFIG_UPDATED, mass_player_id
    )
    expected_features &= ~MediaPlayerEntityFeature.GROUPING
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] == expected_features


async def test_media_image_prefers_current_media(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test entity_picture prefers current_media.image_url over queue."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_group_player_1"
    mass_player_id = "test_group_player_1"

    # The group player has a queue with current_item (which has a static image)
    # and current_media. Set current_media.image_url to a dynamic stream art URL.
    stream_art_url = "https://img.radioparadise.com/covers/l/19806.jpg"
    player = music_assistant_client.players._players[mass_player_id]
    player.current_media = PlayerMedia(
        uri=player.current_media.uri,
        title="Lay It Down",
        artist="Cowboy Junkies",
        image_url=stream_art_url,
    )

    # Also set up get_media_item_image_url to return a static logo URL
    # so we can verify it's NOT used when current_media has an image
    static_logo_url = "https://example.com/station_logo.png"
    music_assistant_client.get_media_item_image_url = MagicMock(
        return_value=static_logo_url
    )

    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_UPDATED, mass_player_id
    )
    state = hass.states.get(entity_id)
    assert state
    # Should use the dynamic stream art, not the static logo
    assert state.attributes["entity_picture"] == stream_art_url
    # Static queue image path should not have been consulted
    music_assistant_client.get_media_item_image_url.assert_not_called()


async def test_media_image_falls_back_to_queue_item(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test entity_picture falls back to queue image when none."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_group_player_1"
    mass_player_id = "test_group_player_1"

    # Set current_media with no image_url
    player = music_assistant_client.players._players[mass_player_id]
    player.current_media = PlayerMedia(
        uri=player.current_media.uri,
        title="Some Track",
        image_url=None,
    )

    # Set up get_media_item_image_url to return a static image
    static_image_url = "https://example.com/album_art.jpg"
    music_assistant_client.get_media_item_image_url = MagicMock(
        return_value=static_image_url
    )

    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_UPDATED, mass_player_id
    )
    state = hass.states.get(entity_id)
    assert state
    # Should fall back to the static queue item image
    assert state.attributes["entity_picture"] == static_image_url
    # Verify the fallback path was actually taken
    music_assistant_client.get_media_item_image_url.assert_called_once()
