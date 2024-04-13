"""Metadata definitions for mocking media library."""

from unittest.mock import MagicMock


class MockMusicServiceItem:
    """Mocks a Soco MusicServiceItem."""

    def __init__(
        self, title: str, item_id: str, parent_id: str, item_class: str, uri: str = None
    ) -> None:
        """Initialize the mock item."""
        self.title = title
        self.item_id = item_id
        self.item_class = item_class
        self.parent_id = parent_id

    def get_uri(self) -> str:
        """Return URI."""
        return self.item_id.replace("S://", "x-file-cifs://")


class MockDidlFavorite(MockMusicServiceItem):
    """Mocks a Soco DidlFavorite."""

    def __init__(
        self,
        title: str,
        item_id: str,
        parent_id: str,
        item_class: str,
        uri: str = None,
        reference_item_id=None,
    ) -> None:
        """Initialize the mock item."""
        MockMusicServiceItem.__init__(self, title, item_id, parent_id, item_class)
        self.reference = MagicMock(name=item_id)
        self.reference.resources.return_value = True
        self.reference.item_id = reference_item_id
        self.reference.get_uri.return_value = uri


mock_sonos_favorites = [
    MockDidlFavorite(
        # Sirius XM
        title="66 - Watercolors",
        item_id="FV:2/4",
        parent_id="FV:2",
        item_class="object.itemobject.item.sonos-favorite",
        uri="x-sonosapi-hls:Api%3atune%3aliveAudio%3ajazzcafe%3aetc",
    ),
    MockDidlFavorite(
        # Pandora
        title="James Taylor Radio",
        item_id="FV:2/13",
        parent_id="FV:2",
        item_class="object.itemobject.item.sonos-favorite",
        uri="x-sonosapi-radio:ST%3aetc",
    ),
    MockDidlFavorite(
        # Sonos Playlists for music library
        title="1984",
        item_id="FV:2/8",
        parent_id="FV:2",
        item_class="object.itemobject.item.sonos-favorite",
        uri="x-rincon-playlist:RINCON_test#A:ALBUMARTIST/Aerosmith/1984",
        reference_item_id="A:ALBUMARTIST/Aerosmith/1984",
    ),
]
