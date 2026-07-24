"""Common fixtures for the Somfy MyLink tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pysomfymylink import Shade
import pytest

from homeassistant.components.somfy_mylink.const import CONF_SYSTEM_ID, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

SYSTEM_ID = "1234567890qwertyuiop"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.somfy_mylink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def shades() -> list[Shade]:
    """Return the covers the fake hub reports."""
    return [
        Shade(target_id="CE1A2B3C.1", name="Left Shade", cover_type=0),
        Shade(target_id="CE1A2B3C.2", name="Right Shade", cover_type=1),
    ]


@pytest.fixture
def mock_somfy_mylink(shades: list[Shade]) -> Generator[MagicMock]:
    """Mock the pysomfymylink client at both import sites."""
    client = MagicMock()
    client.status_info = AsyncMock(return_value=shades)
    client.move_up = AsyncMock(return_value=True)
    client.move_down = AsyncMock(return_value=True)
    client.move_stop = AsyncMock(return_value=True)

    with (
        patch(
            "homeassistant.components.somfy_mylink.SomfyMyLink",
            return_value=client,
        ),
        patch(
            "homeassistant.components.somfy_mylink.config_flow.SomfyMyLink",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="MyLink 192.168.1.10",
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: 44100,
            CONF_SYSTEM_ID: SYSTEM_ID,
        },
    )
