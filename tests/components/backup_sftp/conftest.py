"""PyTest fixtures and test helpers."""

from bcrypt import checkpw, gensalt, hashpw
from getpass import getuser
from io import BytesIO
from typing import AsyncIterator, Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from homeassistant.components.backup_sftp import SFTPConfigEntryData
from homeassistant.components.backup_sftp.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PRIVATE_KEY_FILE,
    CONF_BACKUP_LOCATION,
    DOMAIN
)

from tests.common import MockConfigEntry


CONFIG_ENTRY_TITLE = "SFTP Backup - testsshuser@127.0.0.1:22"
TEST_AGENT_ID = "127.0.0.1.22.testsshuser.tmp.backup.location"

class AsyncFileIteratorMock:
    def __init__(self, content: bytes) -> None:
        self.content = BytesIO(content)

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self

    async def __anext__(self) -> bytes:
        chunk = self.content.read()
        if not chunk:
            try:
                self.content.close()
            finally:
                raise StopAsyncIteration
        return chunk

class SSHServer(asyncssh.SSHServer):
    _backup_location: str | None = None
    _port: int | None = None
    username: str = getuser() if getuser() != "root" else "testuser"
    password: str = "12345678"
    pkey: asyncssh.SSHKey = asyncssh.public_key.generate_private_key(
        alg_name="ssh-rsa",
        comment="Test SSH Key"
    )

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc:
            raise RuntimeError(f"SSH connection error: {str(exc)}")

    def password_auth_supported(self) -> bool:
        return True

    def public_key_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        if username != self.username:
            return False

        return (
            username == self.username and
            checkpw(password.encode(), hashpw(self.password.encode(), gensalt()))
        )

    def validate_public_key(self, username: str, key: asyncssh.SSHKey) -> bool:
        return username == self.username and key == self.pkey


@pytest.fixture()
def async_cm_mock() -> AsyncMock:
    """Test agent list backups."""
    mocked_client = AsyncMock()
    mocked_client.__aenter__ = AsyncMock(return_value=mocked_client)
    mocked_client.__aexit__ = AsyncMock(return_value=None)
    return mocked_client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_AGENT_ID,
        title=CONFIG_ENTRY_TITLE,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 22,
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PRIVATE_KEY_FILE: "private_key",
            CONF_BACKUP_LOCATION: "backup_location"
        },
    )

@pytest.fixture()
def mock_client() -> Generator[MagicMock]:
    """Return a mocked Backup Agent Client."""
    with patch("homeassistant.components.backup_sftp.client.BackupAgentClient") as mocked_client_class:
        # Use an AsyncMock for the client so its async context methods are awaitable
        mocked_client = AsyncMock()
        mocked_client_class.return_value = mocked_client
        
        # When entering the async context, return the client itself
        mocked_client.__aenter__ = AsyncMock(return_value=mocked_client)
        mocked_client.__aexit__ = AsyncMock(return_value=None)
        
        mocked_client.get_identifier = MagicMock(return_value = TEST_AGENT_ID)
        mocked_client.list_backup_location = AsyncMock(return_value=[])
        yield mocked_client
