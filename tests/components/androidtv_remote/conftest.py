"""Fixtures for the Android TV Remote integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.androidtv_remote.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.androidtv_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_unload_entry() -> Generator[AsyncMock, None, None]:
    """Mock unloading a config entry."""
    with patch(
        "homeassistant.components.androidtv_remote.async_unload_entry",
        return_value=True,
    ) as mock_unload_entry:
        yield mock_unload_entry


@pytest.fixture
def mock_api() -> Generator[None, MagicMock, None]:
    """Return a mocked AndroidTVRemote."""
    with patch(
        "homeassistant.components.androidtv_remote.helpers.AndroidTVRemote",
    ) as mock_api_cl:
        mock_api = mock_api_cl.return_value
        mock_api.async_connect = AsyncMock(return_value=None)
        mock_api.device_info = {
            "manufacturer": "My Android TV manufacturer",
            "model": "My Android TV model",
        }
        yield mock_api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Android TV",
        domain=DOMAIN,
        data={"host": "1.2.3.4", "name": "My Android TV", "mac": "1A:2B:3C:4D:5E:6F"},
        unique_id="1a:2b:3c:4d:5e:6f",
        state=ConfigEntryState.NOT_LOADED,
    )
