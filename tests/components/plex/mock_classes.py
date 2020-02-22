"""Mock classes used in tests."""
import itertools

from homeassistant.components.plex.const import CONF_SERVER, CONF_SERVER_IDENTIFIER
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_SERVERS = [
    {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 32400,
        CONF_SERVER: "Plex Server 1",
        CONF_SERVER_IDENTIFIER: "unique_id_123",
    },
    {
        CONF_HOST: "4.3.2.1",
        CONF_PORT: 32400,
        CONF_SERVER: "Plex Server 2",
        CONF_SERVER_IDENTIFIER: "unique_id_456",
    },
]

MOCK_MONITORED_USERS = {
    "a": {"enabled": True},
    "b": {"enabled": False},
    "c": {"enabled": True},
}


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


class MockPlexSystemAccount:
    """Mock a PlexSystemAccount instance."""

    def __init__(self):
        """Initialize the object."""
        self.name = "Dummy"
        self.accountID = 1


class MockPlexServer:
    """Mock a PlexServer instance."""

    def __init__(
        self,
        index=0,
        ssl=True,
        load_users=True,
        num_users=len(MOCK_MONITORED_USERS),
        ignore_new_users=False,
    ):
        """Initialize the object."""
        host = MOCK_SERVERS[index][CONF_HOST]
        port = MOCK_SERVERS[index][CONF_PORT]
        self.friendlyName = MOCK_SERVERS[index][  # pylint: disable=invalid-name
            CONF_SERVER
        ]
        self.machineIdentifier = MOCK_SERVERS[index][  # pylint: disable=invalid-name
            CONF_SERVER_IDENTIFIER
        ]
        prefix = "https" if ssl else "http"
        self._baseurl = f"{prefix}://{host}:{port}"
        self._systemAccount = MockPlexSystemAccount()
        self._ignore_new_users = ignore_new_users
        self._load_users = load_users
        self._num_users = num_users

    def systemAccounts(self):
        """Mock the systemAccounts lookup method."""
        return [self._systemAccount]

    @property
    def accounts(self):
        """Mock the accounts property."""
        return set(["a", "b", "c"])

    @property
    def owner(self):
        """Mock the owner property."""
        return "a"

    @property
    def url_in_use(self):
        """Return URL used by PlexServer."""
        return self._baseurl

    @property
    def version(self):
        """Mock version of PlexServer."""
        return "1.0"

    @property
    def option_monitored_users(self):
        """Mock loaded config option for monitored users."""
        userdict = dict(itertools.islice(MOCK_MONITORED_USERS.items(), self._num_users))
        return userdict if self._load_users else {}

    @property
    def option_ignore_new_shared_users(self):
        """Mock loaded config option for ignoring new users."""
        return self._ignore_new_users

    @property
    def option_show_all_controls(self):
        """Mock loaded config option for showing all controls."""
        return False

    @property
    def option_use_episode_art(self):
        """Mock loaded config option for using episode art."""
        return False
