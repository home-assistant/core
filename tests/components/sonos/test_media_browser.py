"""Tests for the Sonos Media Browser."""

from functools import partial

from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.components.media_player.const import MediaClass, MediaType
from homeassistant.components.sonos.media_browser import (
    build_item_response,
    get_thumbnail_url_full,
)
from homeassistant.core import HomeAssistant

from .conftest import SoCoMockFactory


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
