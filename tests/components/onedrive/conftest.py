"""Fixtures for OneDrive tests."""

from collections.abc import AsyncIterator, Generator
from json import dumps
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.onedrive.const import DOMAIN, OAUTH_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    BACKUP_METADATA,
    CLIENT_ID,
    CLIENT_SECRET,
    MOCK_APPROOT,
    MOCK_BACKUP_FILE,
    MOCK_BACKUP_FOLDER,
    MOCK_DRIVE,
    MOCK_METADATA_FILE,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return OAUTH_SCOPES


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="John Doe's OneDrive",
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
        unique_id="mock_drive_id",
    )


@pytest.fixture
def mock_onedrive_client_init() -> Generator[MagicMock]:
    """Return a mocked GraphServiceClient."""
    with (
        patch(
            "homeassistant.components.onedrive.config_flow.OneDriveClient",
            autospec=True,
        ) as onedrive_client,
        patch(
            "homeassistant.components.onedrive.OneDriveClient",
            new=onedrive_client,
        ),
    ):
        yield onedrive_client


@pytest.fixture(autouse=True)
def mock_onedrive_client(mock_onedrive_client_init: MagicMock) -> Generator[MagicMock]:
    """Return a mocked GraphServiceClient."""
    client = mock_onedrive_client_init.return_value
    client.get_approot.return_value = MOCK_APPROOT
    client.create_folder.return_value = MOCK_BACKUP_FOLDER
    client.list_drive_items.return_value = [MOCK_BACKUP_FILE, MOCK_METADATA_FILE]
    client.get_drive_item.return_value = MOCK_BACKUP_FILE
    client.upload_file.return_value = MOCK_METADATA_FILE

    class MockStreamReader:
        async def iter_chunked(self, chunk_size: int) -> AsyncIterator[bytes]:
            yield b"backup data"

        async def read(self) -> bytes:
            return dumps(BACKUP_METADATA).encode()

    client.download_drive_item.return_value = MockStreamReader()
    client.get_drive.return_value = MOCK_DRIVE
    return client


@pytest.fixture
def mock_large_file_upload_client() -> Generator[AsyncMock]:
    """Return a mocked LargeFileUploadClient upload."""
    with patch(
        "homeassistant.components.onedrive.backup.LargeFileUploadClient.upload"
    ) as mock_upload:
        mock_upload.return_value = MOCK_BACKUP_FILE
        yield mock_upload


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onedrive.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_instance_id() -> Generator[AsyncMock]:
    """Mock the instance ID."""
    with patch(
        "homeassistant.components.onedrive.async_get_instance_id",
        return_value="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0",
    ):
        yield
