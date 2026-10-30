"""Common fixtures for the NX584 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from nx584 import client as nx584_client
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nx584.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

TEST_HOST = "192.168.1.10"
TEST_PORT = 5007


@pytest.fixture
def fake_zones() -> list[dict[str, object]]:
    """Return the zones reported by the fake server."""
    return [
        {"name": "front", "number": 1, "state": False, "bypassed": False},
        {"name": "back", "number": 2, "state": False, "bypassed": False},
        {"name": "inside", "number": 3, "state": False, "bypassed": False},
    ]


@pytest.fixture
def mock_client(fake_zones: list[dict[str, object]]) -> Generator[MagicMock]:
    """Mock the pynx584 client class."""
    with patch.object(nx584_client, "Client") as client_class:
        client = client_class.return_value
        client.list_zones.return_value = fake_zones
        client.list_partitions.return_value = [{"armed": False, "condition_flags": []}]
        client.get_version.return_value = "1.1"
        yield client_class


@pytest.fixture
def mock_watcher() -> Generator[MagicMock]:
    """Mock the zone event watcher thread."""
    with patch(
        "homeassistant.components.nx584.binary_sensor.NX584Watcher"
    ) as watcher_class:
        yield watcher_class


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nx584.async_setup_entry", return_value=None
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="NX584",
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
    )
