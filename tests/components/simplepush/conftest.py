"""Common fixtures for the Simplepush tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.simplepush.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Patch the setup of a config entry."""
    with patch(
        "homeassistant.components.simplepush.async_setup_entry", return_value=None
    ) as mock:
        yield mock


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the client of the current app."""
    with (
        patch("homeassistant.components.simplepush.Client") as mock,
        patch("homeassistant.components.simplepush.config_flow.Client", new=mock),
    ):
        yield mock


@pytest.fixture
def mock_legacy_send() -> Generator[MagicMock]:
    """Mock the send of the old app."""
    with (
        patch("homeassistant.components.simplepush.notify.send") as mock,
        patch("homeassistant.components.simplepush.config_flow.send", new=mock),
    ):
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry of the current app."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Simplepush",
        data={CONF_API_TOKEN: "token"},
        entry_id="app_entry",
    )
