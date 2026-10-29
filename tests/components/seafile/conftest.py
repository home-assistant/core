"""Common fixtures for the Seafile tests."""

from collections.abc import AsyncIterator, Generator
import json
from unittest.mock import AsyncMock, patch

from aioseafile import AccountInfo, DirectoryListing, Library, LibraryDetail
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    load_fixture,
    load_json_array_fixture,
)
import yarl

from homeassistant.components.backup import AgentBackup
from homeassistant.components.seafile.const import (
    CONF_BACKUP,
    CONF_BACKUP_PATH,
    CONF_LIBRARY_ID,
    DOMAIN,
    SUBENTRY_TYPE_LIBRARY,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL

URL = "https://seafile.example.com"
TOKEN = "0123456789abcdef0123456789abcdef01234567"
ACCOUNT_EMAIL = "238e5377def043ab86bb1df2cfffb13d@auth.local"
LIBRARY_ID = "6490a72d-4c26-4020-ad00-1b72fb2c88c9"
ENCRYPTED_LIBRARY_ID = "f7ca59ed-d5bb-4a64-a968-b4d95b33b527"
SUBENTRY_ID = "documents-subentry-id"
BACKUP_PATH = "/Home Assistant backups"
BACKUP_BASE_NAME = "Core_2024.12.0.dev0_2024-11-22_11.48_48727189"
TEST_BACKUP = AgentBackup(
    addons=[],
    backup_id="23e64aec",
    date="2024-11-22T11:48:48.727189+01:00",
    database_included=True,
    extra_metadata={},
    folders=[],
    homeassistant_included=True,
    homeassistant_version="2024.12.0.dev0",
    name="Core 2024.12.0.dev0",
    protected=False,
    size=34519040,
)


def backup_listing(*names: str) -> DirectoryListing:
    """Return a directory listing with the given files."""
    return DirectoryListing.from_dict(
        {
            "dirent_list": [
                {"type": "file", "id": "0" * 40, "name": name, "mtime": 1732272528}
                for name in names
            ]
        }
    )


async def stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Return the chunks as a stream."""
    for chunk in chunks:
        yield chunk


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.seafile.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_seafile_client() -> Generator[AsyncMock]:
    """Mock the aioseafile client used by the coordinator and the config flow."""
    with (
        patch(
            "homeassistant.components.seafile.coordinator.Seafile", autospec=True
        ) as mock_client,
        patch("homeassistant.components.seafile.config_flow.Seafile", new=mock_client),
    ):
        client = mock_client.return_value
        client.get_auth_token.return_value = TOKEN
        client.get_account_info.return_value = AccountInfo.from_json(
            load_fixture("account_info_quota.json", DOMAIN)
        )
        client.get_libraries.return_value = [
            Library.from_dict(library)
            for library in load_json_array_fixture("libraries.json", DOMAIN)
        ]
        client.get_library.return_value = LibraryDetail.from_json(
            load_fixture("library.json", DOMAIN)
        )
        client.get_directory.return_value = backup_listing(
            f"{BACKUP_BASE_NAME}.tar", f"{BACKUP_BASE_NAME}_meta.json"
        )
        client.download_file.side_effect = lambda *_args, **_kwargs: stream(
            json.dumps(TEST_BACKUP.as_dict()).encode()
        )
        client.get_download_link.return_value = yarl.URL(
            f"{URL}/seafhttp/files/token/backup.tar"
        )
        client.download.side_effect = lambda *_args, **_kwargs: stream(
            b"backup ", b"data"
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry with one library."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01K7SEAF1LEENTRY000000000A",
        title="user@example.com (seafile.example.com)",
        data={CONF_URL: URL, CONF_TOKEN: TOKEN, CONF_VERIFY_SSL: True},
        unique_id=ACCOUNT_EMAIL,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_LIBRARY_ID: LIBRARY_ID,
                    CONF_BACKUP: True,
                    CONF_BACKUP_PATH: BACKUP_PATH,
                },
                subentry_type=SUBENTRY_TYPE_LIBRARY,
                title="Documents",
                subentry_id=SUBENTRY_ID,
                unique_id=LIBRARY_ID,
            )
        ],
    )
