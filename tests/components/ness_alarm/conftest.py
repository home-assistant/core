"""Test fixtures for ness_alarm."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ness_alarm.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


class MockClient:
    """Mock nessclient.Client stub."""

    async def panic(self, code):
        """Handle panic."""

    async def disarm(self, code):
        """Handle disarm."""

    async def arm_away(self, code):
        """Handle arm_away."""

    async def arm_home(self, code):
        """Handle arm_home."""

    async def aux(self, output_id, state):
        """Handle auxiliary control."""

    async def keepalive(self):
        """Handle keepalive."""

    async def update(self):
        """Handle update."""

    def on_zone_change(self):
        """Handle on_zone_change."""

    def on_state_change(self):
        """Handle on_state_change."""

    async def close(self):
        """Handle close."""


@pytest.fixture
def mock_nessclient():
    """Mock the nessclient Client constructor.

    Replaces nessclient.Client with a Mock which always returns the same
    MagicMock() instance.
    """
    _mock_instance = MagicMock(MockClient())
    _mock_factory = MagicMock()
    _mock_factory.return_value = _mock_instance

    with patch(
        "homeassistant.components.ness_alarm.Client", new=_mock_factory, create=True
    ):
        yield _mock_instance


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the nessclient Client for config flow tests."""
    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client",
        return_value=AsyncMock(),
    ) as mock:
        yield mock.return_value


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.ness_alarm.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def post_connection_delay() -> Generator[None]:
    """Mock POST_CONNECTION_DELAY to 0 for faster tests."""
    with patch(
        "homeassistant.components.ness_alarm.config_flow.POST_CONNECTION_DELAY",
        0,
    ):
        yield
