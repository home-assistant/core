"""Tests for Google Drive."""

from collections.abc import Awaitable, Callable, Coroutine
import http
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from google_drive_api.exceptions import GoogleDriveApiError
import pytest

from homeassistant.components.google_drive.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

type ComponentSetup = Callable[[], Awaitable[None]]


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    async def func() -> None:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return func


async def test_setup_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    mock_api: MagicMock,
) -> None:
    """Test successful setup and unload."""
    # Setup looks up existing folder to make sure it still exists
    mock_api.list_files = AsyncMock(
        return_value={"files": [{"id": "HA folder ID", "name": "HA folder name"}]}
    )

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert entries[0].state is ConfigEntryState.NOT_LOADED


async def test_create_folder_if_missing(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    mock_api: MagicMock,
) -> None:
    """Test folder is created if missing."""
    # Setup looks up existing folder to make sure it still exists
    # and creates it if missing
    mock_api.list_files = AsyncMock(return_value={"files": []})
    mock_api.create_file = AsyncMock(
        return_value={"id": "new folder id", "name": "Home Assistant"}
    )

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    mock_api.list_files.assert_called_once()
    mock_api.create_file.assert_called_once()


async def test_setup_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    mock_api: MagicMock,
) -> None:
    """Test setup error."""
    # Simulate failure looking up existing folder
    mock_api.list_files = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    mock_api: MagicMock,
) -> None:
    """Test expired token is refreshed."""
    # Setup looks up existing folder to make sure it still exists
    mock_api.list_files = AsyncMock(
        return_value={"files": [{"id": "HA folder ID", "name": "HA folder name"}]}
    )
    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data["token"]["access_token"] == "updated-access-token"
    assert entries[0].data["token"]["expires_in"] == 3600


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        status=status,
    )

    await setup_integration()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is expected_state
