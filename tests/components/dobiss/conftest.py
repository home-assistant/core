"""Shared synthetic Dobiss fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from dobiss_nxt import Light
import pytest
from pytest_homeassistant.common import MockConfigEntry

LIGHTS = (
    Light(4, 0, "Kitchen", True, "Ground floor"),
    Light(2, 0, "Hall", False, "Ground floor"),
)
USER_INPUT = {
    "host": "dobiss.local",
    "api_secret": "synthetic-test-secret-not-a-real-key-123456",
    "ssl": False,
}


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the external API at the library boundary."""
    with (
        patch("homeassistant.components.dobiss.DobissClient", autospec=True) as cls,
        patch("homeassistant.components.dobiss.config_flow.DobissClient", new=cls),
    ):
        client = cls.return_value
        client.discover_lights.return_value = LIGHTS
        client.light_states.return_value = {"4_0": 50, "2_0": 0}
        yield client


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return a configured NXT controller."""
    return MockConfigEntry(domain="dobiss", title="Dobiss", data=USER_INPUT)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent platform setup while testing configuration flows."""
    with patch(
        "homeassistant.components.dobiss.async_setup_entry", return_value=None
    ) as setup:
        yield setup
