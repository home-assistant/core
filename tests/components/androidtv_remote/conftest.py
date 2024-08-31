"""Fixtures for the Android TV Remote integration tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.androidtv_remote.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.androidtv_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_unload_entry() -> Generator[AsyncMock]:
    """Mock unloading a config entry."""
    with patch(
        "homeassistant.components.androidtv_remote.async_unload_entry",
        return_value=True,
    ) as mock_unload_entry:
        yield mock_unload_entry


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
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

        is_on_updated_callbacks: list[Callable] = []
        current_app_updated_callbacks: list[Callable] = []
        volume_info_updated_callbacks: list[Callable] = []
        is_available_updated_callbacks: list[Callable] = []

        def mocked_add_is_on_updated_callback(callback: Callable):
            is_on_updated_callbacks.append(callback)

        def mocked_add_current_app_updated_callback(callback: Callable):
            current_app_updated_callbacks.append(callback)

        def mocked_add_volume_info_updated_callback(callback: Callable):
            volume_info_updated_callbacks.append(callback)

        def mocked_add_is_available_updated_callbacks(callback: Callable):
            is_available_updated_callbacks.append(callback)

        def mocked_is_on_updated(is_on: bool):
            for callback in is_on_updated_callbacks:
                callback(is_on)

        def mocked_current_app_updated(current_app: str):
            for callback in current_app_updated_callbacks:
                callback(current_app)

        def mocked_volume_info_updated(volume_info: dict[str, str | bool]):
            for callback in volume_info_updated_callbacks:
                callback(volume_info)

        def mocked_is_available_updated(is_available: bool):
            for callback in is_available_updated_callbacks:
                callback(is_available)

        mock_api.add_is_on_updated_callback.side_effect = (
            mocked_add_is_on_updated_callback
        )
        mock_api.add_current_app_updated_callback.side_effect = (
            mocked_add_current_app_updated_callback
        )
        mock_api.add_volume_info_updated_callback.side_effect = (
            mocked_add_volume_info_updated_callback
        )
        mock_api.add_is_available_updated_callback.side_effect = (
            mocked_add_is_available_updated_callbacks
        )
        mock_api._on_is_on_updated.side_effect = mocked_is_on_updated
        mock_api._on_current_app_updated.side_effect = mocked_current_app_updated
        mock_api._on_volume_info_updated.side_effect = mocked_volume_info_updated
        mock_api._on_is_available_updated.side_effect = mocked_is_available_updated

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
