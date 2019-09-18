"""Tests for Plex config flow."""
from unittest.mock import MagicMock, Mock, patch, PropertyMock
import plexapi.exceptions
import requests.exceptions

from homeassistant.components.plex import config_flow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_URL

from tests.common import MockConfigEntry


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.PlexFlowHandler()
    flow.hass = hass
    return flow


class MockAvailableServer:  # pylint: disable=too-few-public-methods
    """Mock avilable server objects."""

    def __init__(self, name, client_id):
        """Initialize the object."""
        self.name = name
        self.clientIdentifier = client_id  # pylint: disable=invalid-name
        self.provides = ["server"]


class MockConnection:  # pylint: disable=too-few-public-methods
    """Mock a single account resource connection object."""

    def __init__(self, ssl):
        """Initialize the object."""
        prefix = "https" if ssl else "http"
        self.httpuri = f"{prefix}://1.2.3.4:32400"
        self.uri = "http://4.3.2.1:32400"
        self.local = True


class MockConnections:  # pylint: disable=too-few-public-methods
    """Mock a list of resource connections."""

    def __init__(self, ssl=False):
        """Initialize the object."""
        self.connections = [MockConnection(ssl)]


async def test_bad_credentials(hass):
    """Test when provided credentials are rejected."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexAccount", side_effect=plexapi.exceptions.Unauthorized
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: "12345"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "faulty_credentials"


async def test_import_file_from_discovery(hass):
    """Test importing a legacy file during discovery."""

    mock_file_contents = {
        "1.2.3.4:32400": {"ssl": False, "token": "12345", "verify": True}
    }
    file_host_and_port, file_config = list(mock_file_contents.items())[0]
    used_url = f"http://{file_host_and_port}"

    with patch("plexapi.server.PlexServer") as mock_plex_server, patch(
        "homeassistant.components.plex.config_flow.load_json",
        return_value=mock_file_contents,
    ):
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value="unique_id_123"
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value="Mock Server"
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=used_url)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "discovery"},
            data={CONF_HOST: "1.2.3.4", CONF_PORT: "32400"},
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Mock Server"
        assert result["data"][config_flow.CONF_SERVER] == "Mock Server"
        assert result["data"][config_flow.CONF_SERVER_IDENTIFIER] == "unique_id_123"
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL] == used_url
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN]
            == file_config[CONF_TOKEN]
        )


async def test_discovery(hass):
    """Test starting a flow from discovery."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "discovery"},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: "32400"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_discovery_while_in_progress(hass):
    """Test starting a flow from discovery."""

    await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "discovery"},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: "32400"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import_success(hass):
    """Test a successful configuration import."""

    mock_connections = MockConnections(ssl=True)
    mock_servers = ["Server1"]
    server1 = MockAvailableServer("Server1", "1")

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[server1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.server.PlexServer") as mock_plex_server:
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value="unique_id_123"
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=mock_servers[0]
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "import"},
            data={CONF_TOKEN: "12345", CONF_URL: "https://1.2.3.4:32400"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == mock_servers[0]
    assert result["data"][config_flow.CONF_SERVER] == mock_servers[0]
    assert result["data"][config_flow.CONF_SERVER_IDENTIFIER] == "unique_id_123"
    assert (
        result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
        == mock_connections.connections[0].httpuri
    )


async def test_import_bad_hostname(hass):
    """Test when an invalid address is provided."""

    with patch(
        "plexapi.server.PlexServer", side_effect=requests.exceptions.ConnectionError
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "import"},
            data={CONF_TOKEN: "12345", CONF_URL: "http://1.2.3.4:32400"},
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "not_found"


async def test_unknown_exception(hass):
    """Test when an unknown exception is encountered."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexapi.myplex.MyPlexAccount", side_effect=Exception):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}, data={CONF_TOKEN: "12345"}
        )

        assert result["type"] == "abort"
        assert result["reason"] == "unknown"


async def test_no_servers_found(hass):
    """Test when no servers are on an account."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[])

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: "12345"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "no_servers"


async def test_single_available_server(hass):
    """Test creating an entry with one server available."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_connections = MockConnections()
    mock_servers = ["Server1"]
    server1 = MockAvailableServer("Server1", "1")

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[server1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer"
    ) as mock_plex_server:
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value="unique_id_123"
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=mock_servers[0]
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: "12345"}
        )

        assert result["type"] == "create_entry"
        assert result["title"] == mock_servers[0]
        assert result["data"][config_flow.CONF_SERVER] == mock_servers[0]
        assert result["data"][config_flow.CONF_SERVER_IDENTIFIER] == "unique_id_123"


async def test_multiple_servers_with_selection(hass):
    """Test creating an entry with multiple servers available."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_connections = MockConnections()
    mock_servers = ["Server1", "Server2"]
    server1 = MockAvailableServer("Server1", "1")
    server2 = MockAvailableServer("Server2", "2")

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[server1, server2])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer"
    ) as mock_plex_server:
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value="unique_id_123"
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=mock_servers[0]
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: "12345"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "select_server"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={config_flow.CONF_SERVER: mock_servers[0]}
        )

        assert result["type"] == "create_entry"
        assert result["title"] == mock_servers[0]
        assert result["data"][config_flow.CONF_SERVER] == mock_servers[0]
        assert result["data"][config_flow.CONF_SERVER_IDENTIFIER] == "unique_id_123"


async def test_adding_last_unconfigured_server(hass):
    """Test automatically adding last unconfigured server when multiple servers on account."""

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: "unique_id_456",
            config_flow.CONF_SERVER: "Server2",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_connections = MockConnections()
    mock_servers = ["Server1", "Server2"]
    server1 = MockAvailableServer("Server1", "unique_id_123")
    server2 = MockAvailableServer("Server2", "unique_id_456")

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[server1, server2])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account), patch(
        "plexapi.server.PlexServer"
    ) as mock_plex_server:
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value="unique_id_123"
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=mock_servers[0]
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: "12345"}
        )

        assert result["type"] == "create_entry"
        assert result["title"] == mock_servers[0]
        assert result["data"][config_flow.CONF_SERVER] == mock_servers[0]
        assert result["data"][config_flow.CONF_SERVER_IDENTIFIER] == "unique_id_123"


async def test_already_configured(hass):
    """Test a duplicated successful flow."""

    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={config_flow.CONF_SERVER_IDENTIFIER: "unique_id_123"},
    ).add_to_hass(hass)

    mock_connections = MockConnections()
    mock_servers = ["Server1"]
    server1 = MockAvailableServer("Server1", "1")

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[server1])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.server.PlexServer") as mock_plex_server:
        type(mock_plex_server.return_value).machineIdentifier = PropertyMock(
            return_value="unique_id_123"
        )
        type(mock_plex_server.return_value).friendlyName = PropertyMock(
            return_value=mock_servers[0]
        )
        type(  # pylint: disable=protected-access
            mock_plex_server.return_value
        )._baseurl = PropertyMock(return_value=mock_connections.connections[0].httpuri)
        result = await flow.async_step_import(
            {CONF_TOKEN: "12345", CONF_URL: "http://1.2.3.4:32400"}
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_all_available_servers_configured(hass):
    """Test when all available servers are already configured."""

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: "unique_id_123",
            config_flow.CONF_SERVER: "Server1",
        },
    ).add_to_hass(hass)

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: "unique_id_456",
            config_flow.CONF_SERVER: "Server2",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_connections = MockConnections()
    server1 = MockAvailableServer("Server1", "unique_id_123")
    server2 = MockAvailableServer("Server2", "unique_id_456")

    mm_plex_account = MagicMock()
    mm_plex_account.resources = Mock(return_value=[server1, server2])
    mm_plex_account.resource = Mock(return_value=mock_connections)

    with patch("plexapi.myplex.MyPlexAccount", return_value=mm_plex_account):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: "12345"}
        )

        assert result["type"] == "abort"
        assert result["reason"] == "all_configured"
