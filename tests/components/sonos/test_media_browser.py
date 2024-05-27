"""Tests for the Sonos Media Browser."""

from functools import partial

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.components.media_player.const import MediaClass, MediaType
from homeassistant.components.sonos.media_browser import (
    build_item_response,
    fix_image_url,
    get_thumbnail_url_full,
)
from homeassistant.core import HomeAssistant

from .conftest import SoCoMockFactory

from tests.typing import WebSocketGenerator


class MockMusicServiceItem:
    """Mocks a Soco MusicServiceItem."""

    def __init__(
        self,
        title: str,
        item_id: str,
        parent_id: str,
        item_class: str,
    ) -> None:
        """Initialize the mock item."""
        self.title = title
        self.item_id = item_id
        self.item_class = item_class
        self.parent_id = parent_id

    def get_uri(self) -> str:
        """Return URI."""
        return self.item_id.replace("S://", "x-file-cifs://")


def mock_browse_by_idstring(
    search_type: str, idstring: str, start=0, max_items=100, full_album_art_uri=False
) -> list[MockMusicServiceItem]:
    """Mock the call to browse_by_id_string."""
    if search_type == "albums" and idstring in (
        "A:ALBUM/Abbey%20Road",
        "A:ALBUM/Abbey Road",
    ):
        return [
            MockMusicServiceItem(
                "Come Together",
                "S://192.168.42.10/music/The%20Beatles/Abbey%20Road/01%20Come%20Together.mp3",
                "A:ALBUM/Abbey%20Road",
                "object.item.audioItem.musicTrack",
            ),
            MockMusicServiceItem(
                "Something",
                "S://192.168.42.10/music/The%20Beatles/Abbey%20Road/03%20Something.mp3",
                "A:ALBUM/Abbey%20Road",
                "object.item.audioItem.musicTrack",
            ),
        ]
    return None


async def test_build_item_response(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
) -> None:
    """Test building a browse item response."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")
    soco_mock.music_library.browse_by_idstring = mock_browse_by_idstring
    browse_item: BrowseMedia = build_item_response(
        soco_mock.music_library,
        {"search_type": MediaType.ALBUM, "idstring": "A:ALBUM/Abbey%20Road"},
        partial(
            get_thumbnail_url_full,
            soco_mock.music_library,
            True,
            None,
        ),
    )
    assert browse_item.title == "Abbey Road"
    assert browse_item.media_class == MediaClass.ALBUM
    assert browse_item.media_content_id == "A:ALBUM/Abbey%20Road"
    assert len(browse_item.children) == 2
    assert browse_item.children[0].media_class == MediaClass.TRACK
    assert browse_item.children[0].title == "Come Together"
    assert (
        browse_item.children[0].media_content_id
        == "x-file-cifs://192.168.42.10/music/The%20Beatles/Abbey%20Road/01%20Come%20Together.mp3"
    )
    assert browse_item.children[1].media_class == MediaClass.TRACK
    assert browse_item.children[1].title == "Something"
    assert (
        browse_item.children[1].media_content_id
        == "x-file-cifs://192.168.42.10/music/The%20Beatles/Abbey%20Road/03%20Something.mp3"
    )


async def test_browse_media_root(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_browse_media method."""

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.zone_a",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot


async def test_browse_media_library(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_browse_media method."""

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.zone_a",
            "media_content_id": "",
            "media_content_type": "library",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot


async def test_browse_media_library_albums(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_browse_media method."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.zone_a",
            "media_content_id": "A:ALBUM",
            "media_content_type": "album",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot
    assert soco_mock.music_library.browse_by_idstring.call_count == 1


@pytest.mark.parametrize(
    ("album_art_uri", "expected_result"),
    [
        (
            "http://192.168.42.2:1400/getaa?u=x-file-cifs%3a%2f%2f192.168.42.100%2fmusic%2fCarpenters%2f_Avenue%2520Q_'s%2520Playlist%2f01%2520Rainy%2520Days%2520and%2520Mondays.m4a&v=56",
            "http://192.168.42.2:1400/getaa?u=x-file-cifs://192.168.42.100/music/Carpenters/_Avenue%20Q_%27s%20Playlist/01%20Rainy%20Days%20and%20Mondays.m4a&v=56",
        ),
        (
            "http://192.168.42.2:1400/getaa?u=x-file-cifs%3a%2f%2f192.168.42.100%2fmusic%2fOasis%2f(What's%2520the%2520Story)%2520Morning%2520Glory_%2f03%2520Wonderwall.m4a&v=56",
            "http://192.168.42.2:1400/getaa?u=x-file-cifs://192.168.42.100/music/Oasis/%28What%27s%20the%20Story%29%20Morning%20Glory_/03%20Wonderwall.m4a&v=56",
        ),
        (
            "http://192.168.42.2:1400/getaa?u=x-file-cifs%3a%2f%2f192.168.42.100%2fmusic%2fThe%2520Grateful%2520Dead%2fShakedown%2520Street%2520%2b%2520Bonus%2520Material%2f01%2520Good%2520Lovin'.m4a&v=56",
            "http://192.168.42.2:1400/getaa?u=x-file-cifs://192.168.42.100/music/The%20Grateful%20Dead/Shakedown%20Street%20%2B%20Bonus%20Material/01%20Good%20Lovin%27.m4a&v=56",
        ),
        (
            "http://192.168.42.2:1400/getaa?u=x-file-cifs%3a%2f%2f192.168.42.100%2fmusic%2fiTunes%2520Music%2fSantana%2fAbraxas%2f01%2520Singing%2520Winds,%2520Crying%2520Beasts.m4a&v=56",
            "http://192.168.42.2:1400/getaa?u=x-file-cifs://192.168.42.100/music/iTunes%20Music/Santana/Abraxas/01%20Singing%20Winds%2C%20Crying%20Beasts.m4a&v=56",
        ),
        (
            "http://192.168.42.2:1400/getaa?u=x-file-cifs%3a%2f%2f192.168.42.100%2fmusic%2fCarlos%2520Santana%2520%2526%2520Buddy%2520Miles%2fCarlos%2520Santana%2520%2526%2520Buddy%2520Miles!%2520Live!%2f01%2520Marbles%2520(Live).m4a&v=56",
            "http://192.168.42.2:1400/getaa?u=x-file-cifs://192.168.42.100/music/Carlos%20Santana%20%26%20Buddy%20Miles/Carlos%20Santana%20%26%20Buddy%20Miles%21%20Live%21/01%20Marbles%20%28Live%29.m4a&v=56",
        ),
    ],
)
def test_fix_sonos_image_url(album_art_uri: str, expected_result: str) -> None:
    """Tests processing the image URL targeting specific characters that need encoding."""
    assert fix_image_url(album_art_uri) == expected_result
