"""Fixtures for Homee integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyHomee.model import HomeeAttribute, HomeeNode
import pytest

from homeassistant.components.homee.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

HOMEE_ID = "00055511EECC"
HOMEE_IP = "192.168.1.11"
HOMEE_NAME = "TestHomee"
TESTUSER = "testuser"
TESTPASS = "testpass"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.homee.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=f"{HOMEE_NAME} ({HOMEE_IP})",
        domain=DOMAIN,
        data={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
        },
        unique_id=HOMEE_ID,
    )


@pytest.fixture
def cover() -> HomeeNode:
    """Return a cover mock."""
    att1 = AsyncMock(spec=HomeeAttribute)
    att1.id = 1
    att1.node_id = 1
    att1.instance = 0
    att1.minimum = 0
    att1.maximum = 4
    att1.current_value = 0.0
    att1.unit = "n/a"
    att1.step_value = 1.0
    att1.editable = 1
    att1.type = 135
    att1.state = 1
    att1.changed_by = 1
    att1.data = ""
    att1.name = ""
    att1.is_reversed = 0

    att2 = AsyncMock(spec=HomeeAttribute)
    att2.id = 2
    att2.node_id = 1
    att2.instance = 0
    att2.minimum = 0
    att2.maximum = 100
    att2.current_value = 0.0
    att2.unit = "%"
    att2.step_value = 0.5
    att2.editable = 1
    att2.type = 15
    att2.state = 1
    att2.changed_by = 1
    att2.data = ""
    att2.name = ""
    att2.is_reversed = 0

    att3 = AsyncMock(spec=HomeeAttribute)
    att3.id = 3
    att3.node_id = 1
    att3.instance = 0
    att3.minimum = -45
    att3.maximum = 90
    att3.current_value = -45.0
    att3.unit = "°"
    att3.step_value = 1.0
    att3.editable = 1
    att3.type = 113
    att3.state = 1
    att3.changed_by = 1
    att3.data = ""
    att3.name = ""
    att3.is_reversed = 0

    att1.get_value = lambda: att1.current_value
    att2.get_value = lambda: att2.current_value
    att3.get_value = lambda: att3.current_value

    mock = AsyncMock(spec=HomeeNode)
    mock.id = 1
    mock.name = "Test Cover"
    mock.profile = 2002
    mock.protocol = 23
    mock.state = 1
    mock.attributes = [att1, att2, att3]

    def attribute_by_type(type, instance=0) -> HomeeAttribute | None:
        attrs = {
            135: att1,
            15: att2,
            113: att3,
        }
        return attrs.get(type)

    mock.get_attribute_by_type = attribute_by_type

    return mock


@pytest.fixture
def mock_homee() -> Generator[AsyncMock]:
    """Return a mock Homee instance."""
    with (
        patch(
            "homeassistant.components.homee.config_flow.Homee", autospec=True
        ) as mocked_homee,
        patch(
            "homeassistant.components.homee.Homee",
            new=mocked_homee,
        ),
    ):
        homee = mocked_homee.return_value

        homee.host = HOMEE_IP
        homee.user = TESTUSER
        homee.password = TESTPASS
        homee.settings = MagicMock()
        homee.settings.uid = HOMEE_ID
        homee.settings.homee_name = HOMEE_NAME
        homee.settings.version = "1.2.3"
        homee.settings.mac_address = "00:05:55:11:ee:cc"
        homee.reconnect_interval = 10
        homee.connected = True

        homee.get_access_token.return_value = "test_token"

        yield homee
