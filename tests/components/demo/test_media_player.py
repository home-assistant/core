"""The tests for the Demo Media player platform."""
import pytest
import voluptuous as vol

import homeassistant.components.media_player as mp
from homeassistant.helpers.aiohttp_client import DATA_CLIENTSESSION
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.components.media_player import common

TEST_ENTITY_ID = "media_player.walkman"


@pytest.fixture(name="mock_media_seek")
def media_player_media_seek_fixture():
    """Mock demo YouTube player media seek."""
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_seek",
        autospec=True,
    ) as seek:
        yield seek


async def test_source_select(hass):
    """Test the input source service."""
    entity_id = "media_player.lounge_room"

    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("source") == "dvd"

    with pytest.raises(vol.Invalid):
        await common.async_select_source(hass, None, entity_id)
    state = hass.states.get(entity_id)
    assert state.attributes.get("source") == "dvd"

    await common.async_select_source(hass, "xbox", entity_id)
    state = hass.states.get(entity_id)
    assert state.attributes.get("source") == "xbox"


async def test_clear_playlist(hass):
    """Test clear playlist."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(TEST_ENTITY_ID, "playing")

    await common.async_clear_playlist(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "off")


async def test_volume_services(hass):
    """Test the volume service."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("volume_level") == 1.0

    with pytest.raises(vol.Invalid):
        await common.async_set_volume_level(hass, None, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("volume_level") == 1.0

    await common.async_set_volume_level(hass, 0.5, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("volume_level") == 0.5

    await common.async_volume_down(hass, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("volume_level") == 0.4

    await common.async_volume_up(hass, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("volume_level") == 0.5

    assert False is state.attributes.get("is_volume_muted")

    with pytest.raises(vol.Invalid):
        await common.async_mute_volume(hass, None, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("is_volume_muted") is False

    await common.async_mute_volume(hass, True, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("is_volume_muted") is True


async def test_turning_off_and_on(hass):
    """Test turn_on and turn_off."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(TEST_ENTITY_ID, "playing")

    await common.async_turn_off(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "off")
    assert not mp.is_on(hass, TEST_ENTITY_ID)

    await common.async_turn_on(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "playing")

    await common.async_toggle(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "off")
    assert not mp.is_on(hass, TEST_ENTITY_ID)


async def test_playing_pausing(hass):
    """Test media_pause."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(TEST_ENTITY_ID, "playing")

    await common.async_media_pause(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "paused")

    await common.async_media_play_pause(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "playing")

    await common.async_media_play_pause(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "paused")

    await common.async_media_play(hass, TEST_ENTITY_ID)
    assert hass.states.is_state(TEST_ENTITY_ID, "playing")


async def test_prev_next_track(hass):
    """Test media_next_track and media_previous_track ."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("media_track") == 1

    await common.async_media_next_track(hass, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("media_track") == 2

    await common.async_media_next_track(hass, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("media_track") == 3

    await common.async_media_previous_track(hass, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("media_track") == 2

    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    ent_id = "media_player.lounge_room"
    state = hass.states.get(ent_id)
    assert state.attributes.get("media_episode") == 1

    await common.async_media_next_track(hass, ent_id)
    state = hass.states.get(ent_id)
    assert state.attributes.get("media_episode") == 2

    await common.async_media_previous_track(hass, ent_id)
    state = hass.states.get(ent_id)
    assert state.attributes.get("media_episode") == 1


async def test_play_media(hass):
    """Test play_media ."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    ent_id = "media_player.living_room"
    state = hass.states.get(ent_id)
    assert mp.SUPPORT_PLAY_MEDIA & state.attributes.get("supported_features") > 0
    assert state.attributes.get("media_content_id") is not None

    with pytest.raises(vol.Invalid):
        await common.async_play_media(hass, None, "some_id", ent_id)
    state = hass.states.get(ent_id)
    assert mp.SUPPORT_PLAY_MEDIA & state.attributes.get("supported_features") > 0
    assert state.attributes.get("media_content_id") != "some_id"

    await common.async_play_media(hass, "youtube", "some_id", ent_id)
    state = hass.states.get(ent_id)
    assert mp.SUPPORT_PLAY_MEDIA & state.attributes.get("supported_features") > 0
    assert state.attributes.get("media_content_id") == "some_id"


async def test_seek(hass, mock_media_seek):
    """Test seek."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    ent_id = "media_player.living_room"
    state = hass.states.get(ent_id)
    assert state.attributes["supported_features"] & mp.SUPPORT_SEEK
    assert not mock_media_seek.called
    with pytest.raises(vol.Invalid):
        await common.async_media_seek(hass, None, ent_id)
    assert not mock_media_seek.called

    await common.async_media_seek(hass, 100, ent_id)
    assert mock_media_seek.called


async def test_media_image_proxy(hass, hass_client):
    """Test the media server image proxy server ."""
    assert await async_setup_component(
        hass, mp.DOMAIN, {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    fake_picture_data = "test.test"

    class MockResponse:
        """Test response."""

        def __init__(self):
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

        async def get(self, url):
            """Test websession get."""
            return MockResponse()

        def detach(self):
            """Test websession detach."""

    hass.data[DATA_CLIENTSESSION] = MockWebsession()

    assert hass.states.is_state(TEST_ENTITY_ID, "playing")
    state = hass.states.get(TEST_ENTITY_ID)
    client = await hass_client()
    req = await client.get(state.attributes.get("entity_picture"))
    assert req.status == 200
    assert await req.text() == fake_picture_data
