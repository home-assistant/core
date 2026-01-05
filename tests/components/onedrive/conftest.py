"""Fixtures for OneDrive tests."""

from collections.abc import AsyncIterator, Generator
from html import escape
from json import dumps
import time
from unittest.mock import AsyncMock, MagicMock, patch

from onedrive_personal_sdk.const import DriveState, DriveType
from onedrive_personal_sdk.models.items import (
    AppRoot,
    Drive,
    DriveQuota,
    File,
    Folder,
    Hashes,
    IdentitySet,
    ItemParentReference,
    User,
)
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.onedrive.const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    DOMAIN,
    OAUTH_SCOPES,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import BACKUP_METADATA, CLIENT_ID, CLIENT_SECRET, IDENTITY_SET, INSTANCE_ID

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
            CONF_FOLDER_NAME: "backups_123",
            CONF_FOLDER_ID: "my_folder_id",
        },
        unique_id="mock_drive_id",
        minor_version=2,
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


@pytest.fixture
def mock_approot() -> AppRoot:
    """Return a mocked approot."""
    return AppRoot(
        id="id",
        child_count=0,
        size=0,
        name="name",
        parent_reference=ItemParentReference(
            drive_id="mock_drive_id", id="id", path="path"
        ),
        created_by=IdentitySet(
            user=User(
                display_name="John Doe",
                id="id",
                email="john@doe.com",
            )
        ),
    )


@pytest.fixture
def mock_drive() -> Drive:
    """Return a mocked drive."""
    return Drive(
        id="mock_drive_id",
        name="My Drive",
        drive_type=DriveType.PERSONAL,
        owner=IDENTITY_SET,
        quota=DriveQuota(
            deleted=5,
            remaining=805306368,
            state=DriveState.NEARING,
            total=5368709120,
            used=4250000000,
        ),
    )


@pytest.fixture
def mock_folder() -> Folder:
    """Return a mocked backup folder."""
    return Folder(
        id="my_folder_id",
        name="name",
        size=0,
        child_count=0,
        description="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0",
        parent_reference=ItemParentReference(
            drive_id="mock_drive_id", id="id", path="path"
        ),
        created_by=IdentitySet(
            user=User(
                display_name="John Doe",
                id="id",
                email="john@doe.com",
            ),
        ),
    )


@pytest.fixture
def mock_backup_file() -> File:
    """Return a mocked backup file."""
    return File(
        id="id",
        name="23e64aec.tar",
        size=34519040,
        parent_reference=ItemParentReference(
            drive_id="mock_drive_id", id="id", path="path"
        ),
        hashes=Hashes(
            quick_xor_hash="hash",
        ),
        mime_type="application/x-tar",
        created_by=IDENTITY_SET,
    )


@pytest.fixture
def mock_metadata_file() -> File:
    """Return a mocked metadata file."""
    return File(
        id="id",
        name="23e64aec.tar",
        size=34519040,
        parent_reference=ItemParentReference(
            drive_id="mock_drive_id", id="id", path="path"
        ),
        hashes=Hashes(
            quick_xor_hash="hash",
        ),
        mime_type="application/x-tar",
        description=escape(
            dumps(
                {
                    "metadata_version": 2,
                    "backup_id": "23e64aec",
                    "backup_file_id": "id",
                }
            )
        ),
        created_by=IDENTITY_SET,
    )


@pytest.fixture(autouse=True)
def mock_onedrive_client(
    mock_onedrive_client_init: MagicMock,
    mock_approot: AppRoot,
    mock_drive: Drive,
    mock_folder: Folder,
    mock_backup_file: File,
    mock_metadata_file: File,
) -> Generator[MagicMock]:
    """Return a mocked GraphServiceClient."""
    client = mock_onedrive_client_init.return_value
    client.get_approot.return_value = mock_approot
    client.create_folder.return_value = mock_folder
    client.list_drive_items.return_value = [mock_backup_file, mock_metadata_file]
    client.get_drive_item.return_value = mock_folder
    client.upload_file.return_value = mock_metadata_file

    class MockStreamReader:
        async def iter_chunked(self, chunk_size: int) -> AsyncIterator[bytes]:
            yield b"backup data"

        async def read(self) -> bytes:
            return dumps(BACKUP_METADATA).encode()

    client.download_drive_item.return_value = MockStreamReader()
    client.get_drive.return_value = mock_drive
    return client


@pytest.fixture
def mock_large_file_upload_client(mock_backup_file: File) -> Generator[AsyncMock]:
    """Return a mocked LargeFileUploadClient upload."""
    with patch(
        "homeassistant.components.onedrive.backup.LargeFileUploadClient.upload"
    ) as mock_upload:
        mock_upload.return_value = mock_backup_file
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
    with (
        patch(
            "homeassistant.components.onedrive.async_get_instance_id",
            return_value=INSTANCE_ID,
        ) as mock_instance_id,
        patch(
            "homeassistant.components.onedrive.config_flow.async_get_instance_id",
            new=mock_instance_id,
        ),
    ):
        yield
