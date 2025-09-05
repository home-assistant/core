"""Common fixtures for the SFTPClient tests."""

from collections.abc import Generator
from json import dumps
from types import TracebackType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sftp_client.const import CONF_BACKUP_PATH, DOMAIN
from homeassistant.components.sftp_client.helpers import SFTPConnection
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import BACKUP_METADATA, MOCK_LIST_FILES

from tests.common import MockConfigEntry


class SFTPClientFile:
    """SFTPClientFile object for testing."""

    def __init__(self, path: str) -> None:
        """Initialize the SFTPClientFile."""
        self.path = path
        self._chunks = [b"backup data", b""]
        if path.endswith(".json"):
            self._chunks = [dumps(BACKUP_METADATA).encode("utf-8"), b""]
        self.read = AsyncMock(side_effect=self._chunks)
        self.write = AsyncMock(return_value=None)
        self.close = AsyncMock()


class SFTPClientFileAsyncContextManager(SFTPClientFile):
    """SFTPClientFile async context manager for testing."""

    async def __aenter__(self) -> SFTPClientFile:
        """Return a dummy file-like object."""
        return SFTPClientFile(self.path)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit method."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sftp_client.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="test-username@1.1.1.1",
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_BACKUP_PATH: "backup-folder",
        },
        entry_id="01JKXV07ASC62D620DGYNG2R8H",
    )


def open_side_effect(path, mode):
    """Mock the open method for SFTPClientFile."""
    return SFTPClientFileAsyncContextManager(path)


@pytest.fixture(name="sftp_client")
def mock_sftp_client() -> Generator[AsyncMock]:
    """Mock the sftp client."""
    with patch(
        "homeassistant.components.sftp_client.SFTPConnection", autospec=True
    ) as mock_sftp_client:
        mock = mock_sftp_client.return_value
        mock.async_ssh_connect.return_value = None
        mock.async_connect.return_value = None
        mock.async_close.return_value = None
        mock.async_create_backup_path.return_value = None
        mock.async_ensure_path_exists.return_value = True

        sftp_client_mock = MagicMock(spec=SFTPConnection.client)
        sftp_client_mock.isdir = AsyncMock(return_value=True)
        sftp_client_mock.mkdir = AsyncMock(return_value=True)
        sftp_client_mock.listdir = AsyncMock(return_value=MOCK_LIST_FILES)
        sftp_client_mock.open = AsyncMock(side_effect=open_side_effect)
        sftp_client_mock.remove = AsyncMock(return_value=None)
        sftp_client_mock.rename = AsyncMock(return_value=None)
        sftp_client_mock.exit = MagicMock()

        mock.client = sftp_client_mock
        yield mock
