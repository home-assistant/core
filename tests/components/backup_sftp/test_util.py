"""Tests helpers for SFTP Backup Location component."""

from asyncio import AbstractEventLoop, new_event_loop
from collections.abc import Generator
from io import SEEK_SET, BytesIO
import json
import tarfile
from threading import Thread

import pytest

from homeassistant.components.backup_sftp.util import (
    AsyncSSHFileWrapper,
    process_tar_from_adapter,
)

BACKUP_DATA = {
    "slug": "9e346a5c",
    "version": 2,
    "name": "Automatic backup 2025.2.4",
    "date": "2025-02-21T03:53:34.002185+00:00",
    "type": "partial",
    "supervisor_version": "2025.02.1",
    "extra": {
        "instance_id": "335bb2043172468db48658367b917f87",
        "with_automatic_settings": True,
        "supervisor.backup_request_date": "2025-02-21T04:53:34.000522+01:00",
    },
    "crypto": "aes128",
    "addons": [
        {
            "slug": "ssh",
            "name": "Advanced SSH & Web Terminal",
            "version": "20.0.0",
            "size": 0.0,
        }
    ],
    "repositories": [
        "https://github.com/hacs/addons",
        "https://github.com/hassio-addons/repository",
    ],
    "homeassistant": {"version": "2025.2.4", "exclude_database": False, "size": 0.0},
    "folders": ["share", "media", "ssl"],
    "docker": {"registries": {}},
    "protected": True,
    "compressed": True,
}


class DummyAsyncFile:
    """Dummy class that mimics `SFTPClientFile`."""

    def __init__(self, initial_bytes: bytes):
        """Initialize `DummyAsyncFile`."""
        self._file = BytesIO(initial_bytes)

    async def read(self, size=-1) -> bytes:
        """Implement `read()` method."""
        return self._file.read(size)

    async def seek(self, offset: int, whence: int = SEEK_SET) -> int:
        """Implement `seek()` method."""
        return self._file.seek(offset, whence)

    async def tell(self) -> int:
        """Implement `tell()` method."""
        return self._file.tell()


def create_tar_bytes(files: dict) -> bytes:
    """Create an in-memory tar archive.

    `files` maps file names to their content.
    """
    buf = BytesIO()
    with tarfile.open(mode="w", fileobj=buf) as tar:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(tarinfo=info, fileobj=BytesIO(content))
    return buf.getvalue()


@pytest.fixture
def running_loop() -> Generator[AbstractEventLoop]:
    """Create an asyncio event loop that runs in a background thread.

    This is required because AsyncSSHFileWrapper uses
    asyncio.run_coroutine_threadsafe which needs a running loop.
    """
    loop = new_event_loop()
    thread = Thread(target=loop.run_forever)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join()


@pytest.mark.parametrize(
    ("data_homeassistant"),
    [
        (BACKUP_DATA["homeassistant"]),
        (False),
    ],
)
def test_process_tar_with_valid_backup(
    running_loop: AbstractEventLoop, data_homeassistant: dict | bool
):
    """Test metadata extraction."""
    # Prepare a valid backup.json structure.
    backup_data = BACKUP_DATA.copy()
    backup_data["homeassistant"] = data_homeassistant
    backup_json = json.dumps(backup_data)

    # Create a tar archive with backup.json together with another file.
    tar_bytes = create_tar_bytes(
        {
            "./backup.json": backup_json,
            "other.txt": "This is another file in the archive",
        }
    )

    dummy_async_file = DummyAsyncFile(tar_bytes)
    # Note: We pass the running_loop which is active in a separate thread.
    wrapper = AsyncSSHFileWrapper(dummy_async_file, running_loop)

    result = process_tar_from_adapter(wrapper, "test.tar")

    # Assertions for backup metadata.
    assert result["backup_id"] == backup_data["slug"]
    assert result["date"] == backup_data["date"]
    assert result["extra_metadata"] == backup_data["extra"]
    assert result["name"] == backup_data["name"]
    assert result["protected"] is backup_data["protected"]

    if data_homeassistant:
        assert result["homeassistant_included"] is True
        assert result["database_included"] is True
        assert (
            result["homeassistant_version"] == backup_data["homeassistant"]["version"]
        )
    else:
        assert result["homeassistant_included"] is False
        assert result["database_included"] is False
        assert result["homeassistant_version"] is None

    # Check addons.
    assert len(result["addons"]) == len(backup_data["addons"])
    for addon_obj, expected in zip(
        result["addons"], backup_data["addons"], strict=False
    ):
        assert addon_obj.name == expected["name"]
        assert addon_obj.slug == expected["slug"]
        assert addon_obj.version == expected["version"]

    # Check folders (assuming Folder objects, when cast to str, equal the folder name).
    assert len(result["folders"]) == len(backup_data["folders"])
    for folder_obj, expected in zip(
        result["folders"], backup_data["folders"], strict=False
    ):
        assert str(folder_obj) == expected


def test_process_tar_without_backup_json(running_loop):
    """Test case when backup.json is not in backup archive."""
    # Create a tar archive without the backup.json member.
    tar_bytes = create_tar_bytes({"dummy.txt": "This is a dummy file"})
    dummy_async_file = DummyAsyncFile(tar_bytes)
    wrapper = AsyncSSHFileWrapper(dummy_async_file, running_loop)

    # process_tar_from_adapter should return None when backup.json is missing.
    result = process_tar_from_adapter(wrapper, "test.tar")
    assert result is None


def test_process_tar_with_invalid_json(running_loop):
    """Test case when backup.json is not a valid json file."""
    # Create a tar archive where backup.json contains invalid JSON.
    tar_bytes = create_tar_bytes({"./backup.json": "not a valid json"})
    dummy_async_file = DummyAsyncFile(tar_bytes)
    wrapper = AsyncSSHFileWrapper(dummy_async_file, running_loop)

    # Expect an AssertionError due to invalid JSON in backup.json.
    with pytest.raises(AssertionError) as excinfo:
        process_tar_from_adapter(wrapper, "test.tar")
    assert "cannot be loaded as json" in str(excinfo.value)
