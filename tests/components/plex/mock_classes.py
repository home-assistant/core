"""Mock classes used in tests."""
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

    def __init__(self, index):
        """Initialize the object."""
        self.name = MOCK_SERVERS[index][CONF_SERVER]
        self.clientIdentifier = MOCK_SERVERS[index][  # pylint: disable=invalid-name
            CONF_SERVER_IDENTIFIER
        ]
        self.provides = ["server"]
        self._mock_plex_server = MockPlexServer(index)

    def connect(self, timeout):
        """Mock the resource connect method."""
        return self._mock_plex_server


class MockPlexAccount:
    """Mock a PlexAccount instance."""

    def __init__(self, servers=1):
        """Initialize the object."""
        self._resources = []
        for index in range(servers):
            self._resources.append(MockResource(index))

    def resource(self, name):
        """Mock the PlexAccount resource lookup method."""
        return [x for x in self._resources if x.name == name][0]

    def resources(self):
        """Mock the PlexAccount resources listing method."""
        return self._resources

    def sonos_speaker_by_id(self, machine_identifier):
        """Mock the PlexAccount Sonos lookup method."""
        return MockPlexSonosClient(machine_identifier)


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

    @property
    def library(self):
        """Mock library object of PlexServer."""
        return MockPlexLibrary()

    def playlist(self, playlist):
        """Mock the playlist lookup method."""
        return MockPlexMediaItem(playlist, mediatype="playlist")

    def fetchItem(self, item):
        """Mock the fetchItem method."""
        return MockPlexMediaItem("Item Name")


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
        self._section = MockPlexLibrarySection()

    @property
    def duration(self):
        """Mock the duration attribute."""
        return 10000000

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

    def __init__(self):
        """Initialize the object."""

    def section(self, library_name):
        """Mock the LibrarySection lookup."""
        return MockPlexLibrarySection(library_name)


class MockPlexLibrarySection:
    """Mock a Plex LibrarySection instance."""

    def __init__(self, library="Movies"):
        """Initialize the object."""
        self.title = library

    def get(self, query):
        """Mock the get lookup method."""
        if self.title == "Music":
            return MockPlexArtist(query)
        return MockPlexMediaItem(query)


class MockPlexMediaItem:
    """Mock a Plex Media instance."""

    def __init__(self, title, mediatype="video"):
        """Initialize the object."""
        self.title = str(title)
        self.type = mediatype

    def album(self, album):
        """Mock the album lookup method."""
        return MockPlexMediaItem(album, mediatype="album")

    def track(self, track):
        """Mock the track lookup method."""
        return MockPlexMediaTrack()

    def tracks(self):
        """Mock the tracks lookup method."""
        for index in range(1, 10):
            yield MockPlexMediaTrack(index)

    def episode(self, episode):
        """Mock the episode lookup method."""
        return MockPlexMediaItem(episode, mediatype="episode")

    def season(self, season):
        """Mock the season lookup method."""
        return MockPlexMediaItem(season, mediatype="season")


class MockPlexArtist(MockPlexMediaItem):
    """Mock a Plex Artist instance."""

    def __init__(self, artist):
        """Initialize the object."""
        super().__init__(artist)
        self.type = "artist"

    def get(self, track):
        """Mock the track lookup method."""
        return MockPlexMediaTrack()


class MockPlexMediaTrack(MockPlexMediaItem):
    """Mock a Plex Track instance."""

    def __init__(self, index=1):
        """Initialize the object."""
        super().__init__(f"Track {index}", "track")
        self.index = index


class MockPlexSonosClient:
    """Mock a PlexSonosClient instance."""

    def __init__(self, machine_identifier):
        """Initialize the object."""
        self.machineIdentifier = machine_identifier

    def playMedia(self, item):
        """Mock the playMedia method."""
        pass
