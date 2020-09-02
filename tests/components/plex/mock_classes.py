"""Mock classes used in tests."""
from functools import lru_cache

from aiohttp.helpers import reify
from plexapi.exceptions import NotFound

from homeassistant.components.plex.const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    PLEX_SERVER_CONFIG,
)
from homeassistant.const import CONF_URL

from .const import DEFAULT_DATA, MOCK_SERVERS, MOCK_USERS

GDM_PAYLOAD = [
    {
        "data": {
            "Content-Type": "plex/media-server",
            "Name": "plextest",
            "Port": "32400",
            "Resource-Identifier": "1234567890123456789012345678901234567890",
            "Updated-At": "157762684800",
            "Version": "1.0",
        },
        "from": ("1.2.3.4", 32414),
    }
]


class MockGDM:
    """Mock a GDM instance."""

    def __init__(self):
        """Initialize the object."""
        self.entries = GDM_PAYLOAD

    def scan(self):
        """Mock the scan call."""
        pass


class MockResource:
    """Mock a PlexAccount resource."""

    def __init__(self, index, kind="server"):
        """Initialize the object."""
        if kind == "server":
            self.name = MOCK_SERVERS[index][CONF_SERVER]
            self.clientIdentifier = MOCK_SERVERS[index][  # pylint: disable=invalid-name
                CONF_SERVER_IDENTIFIER
            ]
            self.provides = ["server"]
            self.device = MockPlexServer(index)
        else:
            self.name = f"plex.tv Resource Player {index+10}"
            self.clientIdentifier = f"client-{index+10}"
            self.provides = ["player"]
            self.device = MockPlexClient(f"http://192.168.0.1{index}:32500", index + 10)
            self.presence = index == 0
            self.publicAddressMatches = True

    def connect(self, timeout):
        """Mock the resource connect method."""
        return self.device


class MockPlexAccount:
    """Mock a PlexAccount instance."""

    def __init__(self, servers=1, players=3):
        """Initialize the object."""
        self._resources = []
        for index in range(servers):
            self._resources.append(MockResource(index))
        for index in range(players):
            self._resources.append(MockResource(index, kind="player"))

    def resource(self, name):
        """Mock the PlexAccount resource lookup method."""
        return [x for x in self._resources if x.name == name][0]

    def resources(self):
        """Mock the PlexAccount resources listing method."""
        return self._resources

    def sonos_speaker(self, speaker_name):
        """Mock the PlexAccount Sonos lookup method."""
        return MockPlexSonosClient(speaker_name)


class MockPlexSystemAccount:
    """Mock a PlexSystemAccount instance."""

    def __init__(self, index):
        """Initialize the object."""
        # Start accountIDs at 1 to set proper owner.
        self.name = list(MOCK_USERS)[index]
        self.accountID = index + 1


class MockPlexServer:
    """Mock a PlexServer instance."""

    def __init__(
        self,
        index=0,
        config_entry=None,
        num_users=len(MOCK_USERS),
        session_type="video",
    ):
        """Initialize the object."""
        if config_entry:
            self._data = config_entry.data
        else:
            self._data = DEFAULT_DATA

        self._baseurl = self._data[PLEX_SERVER_CONFIG][CONF_URL]
        self.friendlyName = self._data[CONF_SERVER]
        self.machineIdentifier = self._data[CONF_SERVER_IDENTIFIER]

        self._systemAccounts = list(map(MockPlexSystemAccount, range(num_users)))

        self._clients = []
        self._sessions = []
        self.set_clients(num_users)
        self.set_sessions(num_users, session_type)

        self._cache = {}

    def set_clients(self, num_clients):
        """Set up mock PlexClients for this PlexServer."""
        self._clients = [MockPlexClient(self._baseurl, x) for x in range(num_clients)]

    def set_sessions(self, num_sessions, session_type):
        """Set up mock PlexSessions for this PlexServer."""
        self._sessions = [
            MockPlexSession(self._clients[x], mediatype=session_type, index=x)
            for x in range(num_sessions)
        ]

    def clear_clients(self):
        """Clear all active PlexClients."""
        self._clients = []

    def clear_sessions(self):
        """Clear all active PlexSessions."""
        self._sessions = []

    def clients(self):
        """Mock the clients method."""
        return self._clients

    def sessions(self):
        """Mock the sessions method."""
        return self._sessions

    def systemAccounts(self):
        """Mock the systemAccounts lookup method."""
        return self._systemAccounts

    def url(self, path, includeToken=False):
        """Mock method to generate a server URL."""
        return f"{self._baseurl}{path}"

    @property
    def accounts(self):
        """Mock the accounts property."""
        return set(MOCK_USERS)

    @property
    def version(self):
        """Mock version of PlexServer."""
        return "1.0"

    @reify
    def library(self):
        """Mock library object of PlexServer."""
        return MockPlexLibrary(self)

    def playlist(self, playlist):
        """Mock the playlist lookup method."""
        return MockPlexMediaItem(playlist, mediatype="playlist")

    @lru_cache()
    def playlists(self):
        """Mock the playlists lookup method with a lazy init."""
        return [
            MockPlexPlaylist(
                self.library.section("Movies").all()
                + self.library.section("TV Shows").all()
            ),
            MockPlexPlaylist(self.library.section("Music").all()),
        ]

    def fetchItem(self, item):
        """Mock the fetchItem method."""
        for section in self.library.sections():
            result = section.fetchItem(item)
            if result:
                return result


class MockPlexClient:
    """Mock a PlexClient instance."""

    def __init__(self, url, index=0):
        """Initialize the object."""
        self.machineIdentifier = f"client-{index+1}"
        self._baseurl = url
        self._index = index

    def url(self, key):
        """Mock the url method."""
        return f"{self._baseurl}{key}"

    @property
    def device(self):
        """Mock the device attribute."""
        return "DEVICE"

    @property
    def platform(self):
        """Mock the platform attribute."""
        return "PLATFORM"

    @property
    def product(self):
        """Mock the product attribute."""
        if self._index == 1:
            return "Plex Web"
        return "PRODUCT"

    @property
    def protocolCapabilities(self):
        """Mock the protocolCapabilities attribute."""
        return ["playback"]

    @property
    def state(self):
        """Mock the state attribute."""
        return "playing"

    @property
    def title(self):
        """Mock the title attribute."""
        return "TITLE"

    @property
    def version(self):
        """Mock the version attribute."""
        return "1.0"

    def proxyThroughServer(self, value=True, server=None):
        """Mock the proxyThroughServer method."""
        pass

    def playMedia(self, item):
        """Mock the playMedia method."""
        pass


class MockPlexSession:
    """Mock a PlexServer.sessions() instance."""

    def __init__(self, player, mediatype, index=0):
        """Initialize the object."""
        self.TYPE = mediatype
        self.usernames = [list(MOCK_USERS)[index]]
        self.players = [player]
        self._section = MockPlexLibrarySection("Movies")

    @property
    def duration(self):
        """Mock the duration attribute."""
        return 10000000

    @property
    def librarySectionID(self):
        """Mock the librarySectionID attribute."""
        return 1

    @property
    def ratingKey(self):
        """Mock the ratingKey attribute."""
        return 123

    def section(self):
        """Mock the section method."""
        return self._section

    @property
    def summary(self):
        """Mock the summary attribute."""
        return "SUMMARY"

    @property
    def thumbUrl(self):
        """Mock the thumbUrl attribute."""
        return "http://1.2.3.4/thumb"

    @property
    def title(self):
        """Mock the title attribute."""
        return "TITLE"

    @property
    def type(self):
        """Mock the type attribute."""
        return "movie"

    @property
    def viewOffset(self):
        """Mock the viewOffset attribute."""
        return 0

    @property
    def year(self):
        """Mock the year attribute."""
        return 2020


class MockPlexLibrary:
    """Mock a Plex Library instance."""

    def __init__(self, plex_server):
        """Initialize the object."""
        self._plex_server = plex_server
        self._sections = {}

        for kind in ["Movies", "Music", "TV Shows", "Photos"]:
            self._sections[kind] = MockPlexLibrarySection(kind)

    def section(self, title):
        """Mock the LibrarySection lookup."""
        section = self._sections.get(title)
        if section:
            return section
        raise NotFound

    def sections(self):
        """Return all available sections."""
        return self._sections.values()

    def sectionByID(self, section_id):
        """Mock the sectionByID lookup."""
        return [x for x in self.sections() if x.key == section_id][0]


class MockPlexLibrarySection:
    """Mock a Plex LibrarySection instance."""

    def __init__(self, library):
        """Initialize the object."""
        self.title = library

        if library == "Music":
            self._item = MockPlexArtist("Artist")
        elif library == "TV Shows":
            self._item = MockPlexShow("TV Show")
        else:
            self._item = MockPlexMediaItem(library[:-1])

    def get(self, query):
        """Mock the get lookup method."""
        if self._item.title == query:
            return self._item
        raise NotFound

    def all(self):
        """Mock the all method."""
        return [self._item]

    def fetchItem(self, ratingKey):
        """Return a specific item."""
        for item in self.all():
            if item.ratingKey == ratingKey:
                return item
            if item._children:
                for child in item._children:
                    if child.ratingKey == ratingKey:
                        return child

    @property
    def type(self):
        """Mock the library type."""
        if self.title == "Movies":
            return "movie"
        if self.title == "Music":
            return "artist"
        if self.title == "TV Shows":
            return "show"
        if self.title == "Photos":
            return "photo"

    @property
    def key(self):
        """Mock the key identifier property."""
        return str(id(self.title))

    def update(self):
        """Mock the update call."""
        pass


class MockPlexMediaItem:
    """Mock a Plex Media instance."""

    def __init__(self, title, mediatype="video"):
        """Initialize the object."""
        self.title = str(title)
        self.type = mediatype
        self.thumbUrl = "http://1.2.3.4/thumb.png"
        self._children = []

    def __iter__(self):
        """Provide iterator."""
        yield from self._children

    @property
    def ratingKey(self):
        """Mock the ratingKey property."""
        return id(self.title)


class MockPlexPlaylist(MockPlexMediaItem):
    """Mock a Plex Playlist instance."""

    def __init__(self, items):
        """Initialize the object."""
        super().__init__(f"Playlist ({len(items)} Items)", "playlist")
        for item in items:
            self._children.append(item)


class MockPlexShow(MockPlexMediaItem):
    """Mock a Plex Show instance."""

    def __init__(self, show):
        """Initialize the object."""
        super().__init__(show, "show")
        for index in range(1, 5):
            self._children.append(MockPlexSeason(index))

    def season(self, season):
        """Mock the season lookup method."""
        return [x for x in self._children if x.title == f"Season {season}"][0]


class MockPlexSeason(MockPlexMediaItem):
    """Mock a Plex Season instance."""

    def __init__(self, season):
        """Initialize the object."""
        super().__init__(f"Season {season}", "season")
        for index in range(1, 10):
            self._children.append(MockPlexMediaItem(f"Episode {index}", "episode"))

    def episode(self, episode):
        """Mock the episode lookup method."""
        return self._children[episode - 1]


class MockPlexAlbum(MockPlexMediaItem):
    """Mock a Plex Album instance."""

    def __init__(self, album):
        """Initialize the object."""
        super().__init__(album, "album")
        for index in range(1, 10):
            self._children.append(MockPlexMediaTrack(index))

    def track(self, track):
        """Mock the track lookup method."""
        try:
            return [x for x in self._children if x.title == track][0]
        except IndexError:
            raise NotFound

    def tracks(self):
        """Mock the tracks lookup method."""
        return self._children


class MockPlexArtist(MockPlexMediaItem):
    """Mock a Plex Artist instance."""

    def __init__(self, artist):
        """Initialize the object."""
        super().__init__(artist, "artist")
        self._album = MockPlexAlbum("Album")

    def album(self, album):
        """Mock the album lookup method."""
        return self._album

    def get(self, track):
        """Mock the track lookup method."""
        return self._album.track(track)


class MockPlexMediaTrack(MockPlexMediaItem):
    """Mock a Plex Track instance."""

    def __init__(self, index=1):
        """Initialize the object."""
        super().__init__(f"Track {index}", "track")
        self.index = index


class MockPlexSonosClient:
    """Mock a PlexSonosClient instance."""

    def __init__(self, name):
        """Initialize the object."""
        self.name = name

    def playMedia(self, item):
        """Mock the playMedia method."""
        pass
