"""Test client for SFTP Backup Location component."""

from collections.abc import AsyncGenerator
import io
import json
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, patch

import asyncssh
import pytest

from homeassistant.components.backup import BackupAgentError, suggested_filename
from homeassistant.components.backup.models import AgentBackup

# Import the classes and functions under test.
from homeassistant.components.backup_sftp import SFTPConfigEntryData
from homeassistant.components.backup_sftp.client import (
    AsyncFileIterator,
    BackupAgentClient,
)
from homeassistant.exceptions import ConfigEntryError
from homeassistant.util import slugify

from .conftest import USER_INPUT, create_tar_bytes
from .test_backup import TEST_AGENT_BACKUP
from .test_util import BACKUP_DATA


class DummySFTPFile:
    """Dummy SFTP file class that simulates an async SFTP file interface.

    This class simulates reading, writing, seeking, and other operations
    on a remote SFTP file.
    """

    class DummyStat:
        """Dummy stat object."""

        def __init__(self, content):
            """Initialize `DummyStat` with the provided content."""
            self.size = len(content)

    def __init__(self, content: bytes):
        """Initialize `DummySFTPFile` with the provided content."""
        self.content = content
        self.buffer = io.BytesIO(content)

    async def __aenter__(self):
        """Enter the asynchronous context manager."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit the asynchronous context manager."""

    async def read(self, size=-1):
        """Read up to 'size' bytes from the file."""
        return self.buffer.read(size)

    async def seek(self, offset, whence=io.SEEK_SET):
        """Seek to a specified position in the file."""
        return self.buffer.seek(offset, whence)

    async def tell(self):
        """Return the current file position."""
        return self.buffer.tell()

    async def write(self, data):
        """Write data to the file."""
        self.buffer.write(data)

    async def stat(self) -> DummyStat:
        """Return a dummy stat object containing file size."""
        return self.DummyStat(self.content)

    async def close(self) -> None:
        """Close the file."""
        self.buffer.close()


class DummySFTPClient:
    """Dummy SFTP client that simulates remote SFTP operations.

    This client stores files in an internal dictionary.
    """

    def __init__(self) -> None:
        """Initialize DummySFTPClient with an empty file store."""
        self._files = {}  # Maps full remote file paths to their bytes content

    async def __aenter__(self) -> "DummySFTPClient":
        """Enter the asynchronous context manager."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the asynchronous context manager."""

    def open(self, file, _) -> DummySFTPFile:
        """Open a file from the dummy file store."""
        if file in self._files:
            return DummySFTPFile(self._files[file])
        return DummySFTPFile(b"")

    async def exists(self, file) -> bool:
        """Check if a file exists in the dummy store."""
        return file in self._files

    async def isfile(self, file) -> bool:
        """Check if the given path is a file."""
        return file in self._files

    async def unlink(self, file) -> bool:
        """Remove a file from the dummy store."""
        if file in self._files:
            del self._files[file]

    async def rename(self, file_path, new_name) -> str:
        """Rename a file in the dummy store."""
        if file_path in self._files:
            self._files[new_name] = self._files.pop(file_path)
        return new_name

    async def listdir(self) -> list[str]:
        """List files in the dummy store that have a '.tar' extension."""
        return [path.split("/")[-1] for path in self._files if path.endswith(".tar")]

    async def chdir(self, path) -> None:
        """Simulate changing the current working directory."""
        return


class DummySSHClient:
    """Dummy SSH client that simulates an SSH connection."""

    def __init__(self, sftp_client) -> None:
        """Initialize DummySSHClient with a dummy SFTP client."""
        self._sftp_client = sftp_client

    async def __aenter__(self) -> None:
        """Enter the asynchronous context manager."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the asynchronous context manager."""

    async def start_sftp_client(self) -> "DummySFTPClient":
        """Return the dummy SFTP client."""
        return self._sftp_client


# -----------------------------------------------------------------------------
# Fixture to patch asyncssh.connect and return our dummy SSH/SFTP objects.
# -----------------------------------------------------------------------------
@pytest.fixture
async def dummy_backup_agent_client() -> AsyncGenerator[BackupAgentClient]:
    """Fixture that will create a `BackupAgentClient` with dummy SSH/SFTP connections.

    This fixture patches asyncssh.connect to return a dummy SSH client,
    initializes the `BackupAgentClient`, and yields it for testing.
    """
    cfg = SFTPConfigEntryData(**USER_INPUT)
    dummy_sftp = DummySFTPClient()
    dummy_ssh = DummySSHClient(dummy_sftp)

    async def dummy_connect(*args, **kwargs):
        """Replace asyncssh.connect with a dummy connect function."""
        return dummy_ssh

    # monkeypatch.setattr("homeassistant.components.backup_sftp.client.connect", dummy_connect)

    with (
        NamedTemporaryFile() as f,
        patch("homeassistant.components.backup_sftp.client.connect", dummy_connect),
    ):
        cfg.private_key_file = f.name
        f.write(
            asyncssh.generate_private_key("ssh-rsa").export_private_key("pkcs1-pem")
        )
        f.flush()
        f.seek(0)
        client = BackupAgentClient(cfg)
        await client.__aenter__()
        yield client
        await client.__aexit__(None, None, None)


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------
async def test_get_identifier(dummy_backup_agent_client) -> None:
    """Test that get_identifier returns a properly slugified identifier.

    The identifier should consist of host, port, username, and backup_location,
    joined by periods and slugified.
    """
    client = dummy_backup_agent_client
    identifier = client.get_identifier()
    expected = slugify(
        ".".join(
            [
                client.cfg.host,
                str(client.cfg.port),
                client.cfg.username,
                client.cfg.backup_location,
            ]
        )
    )
    assert identifier == expected


async def test_async_list_backups(dummy_backup_agent_client) -> None:
    """Test that async_list_backups returns a list of AgentBackup objects from tar archives.

    This test creates a tar archive containing a valid backup.json (together with an extra file)
    and places it in the dummy SFTP client's storage. It then verifies that the backup metadata
    is correctly extracted and that the file size matches.
    """
    client = dummy_backup_agent_client
    backup_data = BACKUP_DATA
    backup_json = json.dumps(backup_data)
    tar_bytes = create_tar_bytes(
        {"./backup.json": backup_json, "other.txt": "dummy content"}
    )
    file_path = f"{client.cfg.backup_location}/backup1.tar"
    client.sftp._files[file_path] = tar_bytes

    async def dummy_listdir():
        """Replace listdir function returning the tar file name in a list."""
        return [file_path.split("/")[-1]]

    client.sftp.listdir = dummy_listdir

    async def dummy_chdir(path):
        """Replace chdir function that does nothing."""
        return

    client.sftp.chdir = dummy_chdir

    async def dummy_rename(old, new):
        """Replace rename function that renames the file in the dummy store."""
        client.sftp._files[new] = client.sftp._files.pop(old)
        return new

    client.sftp.rename = dummy_rename

    backups = await client.async_list_backups()
    # Expect one backup to be returned.
    assert len(backups) == 1
    backup = backups[0]
    assert backup.backup_id == backup_data["slug"]
    file_name = "backup_location/" + suggested_filename(backup)
    assert (
        await client.rename(file_name, file_name) == file_name
    )  # Cheap trick to gain more coverage.

    # Attempt to run `process_tar_from_adapter` with errors
    with patch(
        "homeassistant.components.backup_sftp.client.process_tar_from_adapter"
    ) as mck:
        mck.return_value = None
        backups = await client.async_list_backups()
        assert len(backups) == 0

        mck.side_effect = AssertionError("Error message")
        backups = await client.async_list_backups()
        assert len(backups) == 0


async def test_async_delete_backup(dummy_backup_agent_client) -> None:
    """Test that async_delete_backup successfully deletes a backup file from remote SFTP storage.

    This test creates a dummy tar archive in the dummy SFTP client's storage, calls
    async_delete_backup, and verifies that the file has been removed.
    """

    async def exists_is_file(_):
        """Replace `client.sftp.exists` and `client.sftp.isfile` methods with async function that returns always True."""
        return True

    client = dummy_backup_agent_client
    backup_data = TEST_AGENT_BACKUP.as_dict()
    backup_json = json.dumps(backup_data)
    tar_bytes = create_tar_bytes({"./backup.json": backup_json})
    file_path = f"{client.cfg.backup_location}/{suggested_filename(AgentBackup(**{**backup_data, 'size': len(tar_bytes)}))}"
    client.sftp._files[file_path] = tar_bytes

    # Patch exists and isfile to return True.
    client.sftp.exists = exists_is_file
    client.sftp.isfile = exists_is_file

    backup = AgentBackup(**{**backup_data, "size": len(tar_bytes)})
    await client.async_delete_backup(backup)
    assert file_path not in client.sftp._files


async def test_async_upload_backup(dummy_backup_agent_client) -> None:
    """Test that async_upload_backup writes data from an async iterator to remote SFTP storage."""
    client = dummy_backup_agent_client

    async def dummy_iterator():
        """Async iterator yielding byte chunks."""
        for chunk in [b"chunk1-", b"chunk2-", b"chunk3"]:
            yield chunk

    backup_data = TEST_AGENT_BACKUP.as_dict()
    # Create a dummy AgentBackup. Size is not used during upload.
    backup = AgentBackup(**{**backup_data, "size": 0})

    # Call async_upload_backup with the dummy iterator.
    await client.async_upload_backup(dummy_iterator(), backup)


async def test_raised_exceptions(dummy_backup_agent_client) -> None:
    """Test some cases where exceptions will be raised."""
    cfg = SFTPConfigEntryData(**USER_INPUT)
    cfg.password = None
    cfg.private_key_file = None
    try:
        client = BackupAgentClient(cfg)
    except ConfigEntryError:
        pass
    except Exception as e:
        raise AssertionError("Wrong exception encountered.") from e
    else:
        raise AssertionError("Initialization succeeded instead of failed.")

    cfg.password = "password"
    client = BackupAgentClient(cfg)
    # This will fail because _ssh and sftp attributes are None
    with pytest.raises(RuntimeError) as excinfo:
        client._initialized()
    assert "Connection is not initialized" in str(excinfo)

    # We set value to _ssh
    client._ssh = True
    with pytest.raises(RuntimeError) as excinfo:
        client._initialized()
    assert "Connection is not initialized" in str(excinfo)

    # We set value to _sftp

    client._ssh = None
    client.sftp = True
    with pytest.raises(RuntimeError) as excinfo:
        client._initialized()
    assert "Connection is not initialized" in str(excinfo)

    # Now we try to induce RuntimeError for incorrect file_path
    client._ssh = True
    client.sftp = True
    with pytest.raises(RuntimeError) as excinfo:
        client._initialized("none_file")
    assert "Attempted to access file outside of configured backup location" in str(
        excinfo
    )

    client = dummy_backup_agent_client
    with pytest.raises(AssertionError) as excinfo:
        await client.iter_file(None)
    assert "None object passed" in str(excinfo)

    backup_data = TEST_AGENT_BACKUP.as_dict()
    backup = AgentBackup(**{**backup_data, "size": 0})
    with pytest.raises(BackupAgentError) as excinfo:
        await client.iter_file(backup)
    assert "Backup not found" in str(excinfo)

    client.sftp.isfile = AsyncMock(return_value=True)
    result = await client.iter_file(backup)
    assert isinstance(result, AsyncFileIterator)

    with pytest.raises(RuntimeError) as excinfo:
        async with client.open("file"):
            pass
    assert "Attempted to access file outside of configured backup location:" in str(
        excinfo
    )


async def test_client_open(dummy_backup_agent_client) -> None:
    """Test if we can open a file and return file-like object."""
    client = dummy_backup_agent_client
    async with client.open("backup_location/file") as f:
        assert isinstance(f, DummySFTPFile)


async def test_async_file_iterator(dummy_backup_agent_client) -> None:
    """Run tests for `AsyncFileIterator`."""
    cfg = SFTPConfigEntryData(**USER_INPUT)
    with patch(
        "homeassistant.components.backup_sftp.client.BackupAgentClient"
    ) as client:
        client.return_value = dummy_backup_agent_client
        dummy_backup_agent_client.sftp.open = AsyncMock()
        iterator = AsyncFileIterator(cfg, "file_path", buffer_size=1)

        # This one will not work, as iterator will setup
        # _fileobj. We want this to gain more coverage.
        async for b in iterator:
            assert isinstance(b, AsyncMock)
            break

        # Now the actual test.
        iterator._fileobj = DummySFTPFile(b"12")
        async for b in iterator:
            try:
                int(b.decode())
            except Exception as e:
                raise AssertionError(f"Could not transfer {b} to int.") from e
