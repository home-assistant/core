"""Fixtures for the ISY994 tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyisy.nodes import Node
import pytest

from homeassistant.components.isy994.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_UUID = "00:00:00:00:00:00"


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        unique_id=MOCK_UUID,
    )


@pytest.fixture
def mock_isy():
    """Return a mock ISY object."""
    mock = MagicMock()
    mock.nodes = MagicMock()
    mock.nodes.__iter__.return_value = []
    mock.nodes.status_events = MagicMock()
    mock.programs = MagicMock()
    mock.programs.get_by_name.return_value = None
    mock.variables = MagicMock()
    mock.variables.children = []
    mock.networking = MagicMock()
    mock.networking.nobjs = []
    mock.clock = MagicMock()
    mock.websocket = MagicMock()
    mock.conf = {
        "name": "Skynet ISY",
        "model": "IoX",
        "firmware": "6.0.4",
        "Networking Module": True,
        "Portal": True,
    }
    mock.uuid = MOCK_UUID
    mock.conn.url = "http://1.1.1.1:80"
    mock.initialize = AsyncMock()
    return mock


@pytest.fixture
def mock_node():
    """Return a mock ISY node."""

    def _mock_node(isy, address, name, node_def_id, node_type=None):
        node = MagicMock(spec=Node)
        node.isy = isy
        node.address = address
        node.name = name
        node.node_def_id = node_def_id
        node.type = node_type
        node.status = 0
        node.uom = None
        node.prec = 0
        node.protocol = "insteon"
        node.folder = None
        node.parent_node = None
        node.primary_node = address
        node.aux_properties = {}
        node.status_events = MagicMock()
        node.status_events.subscribe.return_value = MagicMock()
        node.control_events = MagicMock()
        node.control_events.subscribe.return_value = MagicMock()
        node.is_backlight_supported = False
        return node

    return _mock_node


@pytest.fixture(autouse=True)
def mock_isy_init(mock_isy):
    """Mock pyisy.ISY initialization."""
    with (
        patch("homeassistant.components.isy994.ISY", return_value=mock_isy),
        patch(
            "homeassistant.components.isy994.config_flow.Connection.test_connection",
            return_value="<configuration></configuration>",
        ),
    ):
        yield mock_isy
