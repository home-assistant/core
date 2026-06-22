"""Common fixtures for the Steam integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.steam_online.const import DOMAIN

from . import ACCOUNT_1, CONF_DATA, CONF_OPTIONS

from tests.common import MockConfigEntry, patch


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Steam configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options=CONF_OPTIONS,
        unique_id=ACCOUNT_1,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.steam_online.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
