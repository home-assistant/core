"""The tests for the Demo Media player platform."""

from http import HTTPStatus
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator

from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntityFeature,
    MediaPlayerService,
    MediaPlayerServiceArgument,
    RepeatMode,
    is_on,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import DATA_CLIENTSESSION, _make_key
from homeassistant.setup import async_setup_component

TEST_ENTITY_ID = "media_player.walkman"


@pytest.fixture(autouse=True)
def autouse_disable_platforms(disable_platforms):
    """Auto use the disable_platforms fixture."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.fixture(name="mock_media_seek")
def media_player_media_seek_fixture():
    """Mock demo YouTube player media seek."""
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_seek",
        autospec=True,
    ) as seek:
        yield seek


async def test_source_select(hass: HomeAssistant) -> None:
    """Test the input source service."""
    entity_id = "media_player.lounge_room"

    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "dvd"

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            MP_DOMAIN,
            MediaPlayerService.SELECT_SOURCE,
            {TargetKey.ENTITY_ID: entity_id, MediaPlayerServiceArgument.SOURCE: None},
            blocking=True,
        )
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "dvd"

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.SELECT_SOURCE,
        {TargetKey.ENTITY_ID: entity_id, MediaPlayerServiceArgument.SOURCE: "xbox"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "xbox"


async def test_repeat_set(hass: HomeAssistant) -> None:
    """Test the repeat set service."""
    entity_id = "media_player.walkman"

    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_MEDIA_REPEAT) == RepeatMode.OFF

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.REPEAT_SET,
        {
            TargetKey.ENTITY_ID: entity_id,
            MediaPlayerServiceArgument.REPEAT: RepeatMode.ALL,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_MEDIA_REPEAT) == RepeatMode.ALL


async def test_clear_playlist(hass: HomeAssistant) -> None:
    """Test clear playlist."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.CLEAR_PLAYLIST,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_volume_services(hass: HomeAssistant) -> None:
    """Test the volume service."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 1.0

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            MP_DOMAIN,
            MediaPlayerService.VOLUME_SET,
            {
                TargetKey.ENTITY_ID: TEST_ENTITY_ID,
                MediaPlayerServiceArgument.VOLUME_LEVEL: None,
            },
            blocking=True,
        )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 1.0

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.VOLUME_SET,
        {
            TargetKey.ENTITY_ID: TEST_ENTITY_ID,
            MediaPlayerServiceArgument.VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0.5

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.VOLUME_DOWN,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0.4

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.VOLUME_UP,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0.5

    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is False

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            MP_DOMAIN,
            MediaPlayerService.VOLUME_MUTE,
            {
                TargetKey.ENTITY_ID: TEST_ENTITY_ID,
                MediaPlayerServiceArgument.IS_VOLUME_MUTED: None,
            },
            blocking=True,
        )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is False

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.VOLUME_MUTE,
        {
            TargetKey.ENTITY_ID: TEST_ENTITY_ID,
            MediaPlayerServiceArgument.IS_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True


async def test_turning_off_and_on(hass: HomeAssistant) -> None:
    """Test turn_on and turn_off."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.TURN_OFF,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF
    assert not is_on(hass, TEST_ENTITY_ID)

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.TURN_ON,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING
    assert is_on(hass, TEST_ENTITY_ID)

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.TOGGLE,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF
    assert not is_on(hass, TEST_ENTITY_ID)


async def test_playing_pausing(hass: HomeAssistant) -> None:
    """Test media_pause."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_PAUSE,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PAUSED

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_PLAY_PAUSE,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_PLAY_PAUSE,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PAUSED

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_PLAY,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING


async def test_prev_next_track(hass: HomeAssistant) -> None:
    """Test media_next_track and media_previous_track ."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_TRACK) == 1

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_NEXT_TRACK,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_TRACK) == 2

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_NEXT_TRACK,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_TRACK) == 3

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_PREVIOUS_TRACK,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(ATTR_MEDIA_TRACK) == 2

    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    ent_id = "media_player.lounge_room"
    state = hass.states.get(ent_id)
    assert state.attributes.get(ATTR_MEDIA_EPISODE) == "1"

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_NEXT_TRACK,
        {TargetKey.ENTITY_ID: ent_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ent_id)
    assert state.attributes.get(ATTR_MEDIA_EPISODE) == "2"

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_PREVIOUS_TRACK,
        {TargetKey.ENTITY_ID: ent_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ent_id)
    assert state.attributes.get(ATTR_MEDIA_EPISODE) == "1"


async def test_play_media(hass: HomeAssistant) -> None:
    """Test play_media ."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    ent_id = "media_player.living_room"
    state = hass.states.get(ent_id)
    assert (
        MediaPlayerEntityFeature.PLAY_MEDIA
        & state.attributes.get(ATTR_SUPPORTED_FEATURES)
        > 0
    )
    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) is not None

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            MP_DOMAIN,
            MediaPlayerService.PLAY_MEDIA,
            {
                TargetKey.ENTITY_ID: ent_id,
                MediaPlayerServiceArgument.MEDIA_CONTENT_ID: "some_id",
            },
            blocking=True,
        )
    state = hass.states.get(ent_id)
    assert (
        MediaPlayerEntityFeature.PLAY_MEDIA
        & state.attributes.get(ATTR_SUPPORTED_FEATURES)
        > 0
    )
    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) != "some_id"

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.PLAY_MEDIA,
        {
            TargetKey.ENTITY_ID: ent_id,
            MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE: "youtube",
            MediaPlayerServiceArgument.MEDIA_CONTENT_ID: "some_id",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ent_id)
    assert (
        MediaPlayerEntityFeature.PLAY_MEDIA
        & state.attributes.get(ATTR_SUPPORTED_FEATURES)
        > 0
    )
    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) == "some_id"


async def test_seek(hass: HomeAssistant, mock_media_seek) -> None:
    """Test seek."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    ent_id = "media_player.living_room"
    state = hass.states.get(ent_id)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & MediaPlayerEntityFeature.SEEK
    assert not mock_media_seek.called

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            MP_DOMAIN,
            MediaPlayerService.MEDIA_SEEK,
            {
                TargetKey.ENTITY_ID: ent_id,
                MediaPlayerServiceArgument.SEEK_POSITION: None,
            },
            blocking=True,
        )
    assert not mock_media_seek.called

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_SEEK,
        {
            TargetKey.ENTITY_ID: ent_id,
            MediaPlayerServiceArgument.SEEK_POSITION: 100,
        },
        blocking=True,
    )
    assert mock_media_seek.called


async def test_stop(hass: HomeAssistant) -> None:
    """Test stop."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.MEDIA_STOP,
        {TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_media_image_proxy(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the media server image proxy server ."""
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    fake_picture_data = "test.test"

    class MockResponse:
        """Test response."""

        def __init__(self) -> None:
            """Test response init."""
            self.status = 200
            self.headers = {"Content-Type": "sometype"}

        async def read(self):
            """Test response read."""
            return fake_picture_data.encode("ascii")

        async def release(self):
            """Test response release."""

    class MockWebsession:
        """Test websession."""

        async def get(self, url, **kwargs):
            """Test websession get."""
            return MockResponse()

        def detach(self):
            """Test websession detach."""

    hass.data[DATA_CLIENTSESSION] = {_make_key(): MockWebsession()}

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_PLAYING
    client = await hass_client()
    req = await client.get(state.attributes.get(ATTR_ENTITY_PICTURE))
    assert req.status == HTTPStatus.OK
    assert await req.text() == fake_picture_data


async def test_grouping(hass: HomeAssistant) -> None:
    """Test the join/unjoin services."""
    walkman = "media_player.walkman"
    kitchen = "media_player.kitchen"

    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    state = hass.states.get(walkman)
    assert state.attributes.get(ATTR_GROUP_MEMBERS) == []

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.JOIN,
        {
            TargetKey.ENTITY_ID: walkman,
            MediaPlayerServiceArgument.GROUP_MEMBERS: [
                kitchen,
            ],
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(walkman)
    assert state.attributes.get(ATTR_GROUP_MEMBERS) == [walkman, kitchen]

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.UNJOIN,
        {TargetKey.ENTITY_ID: walkman},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(walkman)
    assert state.attributes.get(ATTR_GROUP_MEMBERS) == []


async def test_browse(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the media player browse."""
    entity = "media_player.browse"

    await async_setup_component(hass, "media_source", {"media_source": {}})
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": entity,
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["success"]
    assert msg["result"]["title"] == "media"
    assert msg["result"]["media_class"] == "directory"
    assert len(msg["result"]["children"])


async def test_search(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the media player search delegates to media source."""
    entity = "media_player.browse"

    await async_setup_component(hass, "media_source", {"media_source": {}})
    assert await async_setup_component(
        hass, MP_DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "media_player/search_media",
            "entity_id": entity,
            "search_query": "test",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["success"]
    assert [item["title"] for item in msg["result"]["result"]] == ["test.mp3"]
