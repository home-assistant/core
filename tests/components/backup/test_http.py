"""Tests for the Backup integration."""

import asyncio
from collections.abc import AsyncIterator
from io import BytesIO, StringIO
import json
import tarfile
from typing import Any
from unittest.mock import patch

from aiohttp import web
import pytest

from homeassistant.components.backup import (
    AddonInfo,
    AgentBackup,
    BackupAgentError,
    BackupNotFound,
    Folder,
)
from homeassistant.components.backup.const import DOMAIN
from homeassistant.core import HomeAssistant

from .common import TEST_BACKUP_ABC123, aiter_from_iter, setup_backup_integration

from tests.common import MockUser, get_fixture_path
from tests.typing import ClientSessionGenerator

PROTECTED_BACKUP = AgentBackup(
    addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
    backup_id="c0cb53bd",
    database_included=True,
    date="1970-01-01T00:00:00Z",
    extra_metadata={},
    folders=[Folder.MEDIA, Folder.SHARE],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Test",
    protected=True,
    size=13,
)


async def test_downloading_local_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test downloading a local backup file."""
    await setup_backup_integration(hass)

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.backup.CoreLocalBackupAgent.async_get_backup",
            return_value=TEST_BACKUP_ABC123,
        ),
        patch(
            "homeassistant.components.backup.backup.CoreLocalBackupAgent.get_backup_path",
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "homeassistant.components.backup.http.FileResponse",
            return_value=web.Response(text=""),
        ),
    ):
        resp = await client.get("/api/backup/download/abc123?agent_id=backup.local")
        assert resp.status == 200


async def test_downloading_remote_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test downloading a remote backup."""

    await setup_backup_integration(
        hass, backups={"test.test": [TEST_BACKUP_ABC123]}, remote_agents=["test.test"]
    )

    client = await hass_client()

    resp = await client.get("/api/backup/download/abc123?agent_id=test.test")
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"


async def test_downloading_local_encrypted_backup_file_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test downloading a local backup file."""
    await setup_backup_integration(hass)
    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.backup.CoreLocalBackupAgent.async_get_backup",
            return_value=TEST_BACKUP_ABC123,
        ),
        patch(
            "homeassistant.components.backup.backup.CoreLocalBackupAgent.get_backup_path",
        ),
    ):
        resp = await client.get(
            "/api/backup/download/abc123?agent_id=backup.local&password=blah"
        )
        assert resp.status == 404


@pytest.mark.usefixtures("mock_backups")
async def test_downloading_local_encrypted_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test downloading a local backup file."""
    await setup_backup_integration(hass)
    await _test_downloading_encrypted_backup(hass_client, "backup.local")


async def test_downloading_remote_encrypted_backup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test downloading a local backup file."""
    backup_path = get_fixture_path("test_backups/c0cb53bd.tar", DOMAIN)
    mock_agents = await setup_backup_integration(
        hass, remote_agents=["test.test"], backups={"test.test": [PROTECTED_BACKUP]}
    )

    async def download_backup(backup_id: str, **kwargs: Any) -> AsyncIterator[bytes]:
        return aiter_from_iter((backup_path.read_bytes(),))

    mock_agents["test.test"].async_download_backup.side_effect = download_backup
    await _test_downloading_encrypted_backup(hass_client, "test.test")


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (BackupAgentError, 500),
        (BackupNotFound, 404),
    ],
)
async def test_downloading_remote_encrypted_backup_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    error: Exception,
    status: int,
) -> None:
    """Test downloading a local backup file."""
    mock_agents = await setup_backup_integration(
        hass, remote_agents=["test.test"], backups={"test.test": [PROTECTED_BACKUP]}
    )

    mock_agents["test.test"].async_download_backup.side_effect = error
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{PROTECTED_BACKUP.backup_id}?agent_id=test.test&password=blah"
    )
    assert resp.status == status


async def _test_downloading_encrypted_backup(
    hass_client: ClientSessionGenerator,
    agent_id: str,
) -> None:
    """Test downloading an encrypted backup file."""
    # Try downloading without supplying a password
    client = await hass_client()
    resp = await client.get(f"/api/backup/download/c0cb53bd?agent_id={agent_id}")
    assert resp.status == 200
    backup = await resp.read()
    # We expect a valid outer tar file, but the inner tar file is encrypted and
    # can't be read
    with tarfile.open(fileobj=BytesIO(backup), mode="r") as outer_tar:
        enc_metadata = json.loads(outer_tar.extractfile("./backup.json").read())
        assert enc_metadata["protected"] is True
        with (
            outer_tar.extractfile("homeassistant.tar.gz") as inner_tar_file,
            pytest.raises(tarfile.ReadError, match="file could not be opened"),
        ):
            # pylint: disable-next=consider-using-with
            tarfile.open(fileobj=inner_tar_file, mode="r")

    # Download with the wrong password
    resp = await client.get(
        f"/api/backup/download/c0cb53bd?agent_id={agent_id}&password=wrong"
    )
    assert resp.status == 200
    backup = await resp.read()
    # We expect a truncated outer tar file
    with (
        tarfile.open(fileobj=BytesIO(backup), mode="r") as outer_tar,
        pytest.raises(tarfile.ReadError, match="unexpected end of data"),
    ):
        outer_tar.getnames()

    # Finally download with the correct password
    resp = await client.get(
        f"/api/backup/download/c0cb53bd?agent_id={agent_id}&password=hunter2"
    )
    assert resp.status == 200
    backup = await resp.read()
    # We expect a valid outer tar file, the inner tar file is decrypted and can be read
    with (
        tarfile.open(fileobj=BytesIO(backup), mode="r") as outer_tar,
    ):
        dec_metadata = json.loads(outer_tar.extractfile("./backup.json").read())
        assert dec_metadata == enc_metadata | {"protected": False}
        with (
            outer_tar.extractfile("homeassistant.tar.gz") as inner_tar_file,
            tarfile.open(fileobj=inner_tar_file, mode="r") as inner_tar,
        ):
            assert inner_tar.getnames() == [
                ".",
                "README.md",
                "test_symlink",
                "test1",
                "test1/script.sh",
            ]


async def test_downloading_backup_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test downloading a backup file that does not exist."""
    await setup_backup_integration(hass)

    client = await hass_client()

    resp = await client.get("/api/backup/download/abc123?agent_id=backup.local")
    assert resp.status == 404


async def test_downloading_backup_not_found_get_backup_returns_none(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test downloading a backup file that does not exist."""
    mock_agents = await setup_backup_integration(hass, remote_agents=["test.test"])
    mock_agents["test.test"].async_get_backup.return_value = None
    mock_agents["test.test"].async_get_backup.side_effect = None

    client = await hass_client()

    resp = await client.get("/api/backup/download/abc123?agent_id=test.test")
    assert resp.status == 404
    assert (
        "Detected that integration 'test' returns None from BackupAgent.async_get_backup."
        in caplog.text
    )


async def test_downloading_as_non_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test downloading a backup file when you are not an admin."""
    hass_admin_user.groups = []
    await setup_backup_integration(hass)

    client = await hass_client()

    resp = await client.get("/api/backup/download/abc123?agent_id=backup.local")
    assert resp.status == 401


async def test_uploading_a_backup_file(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test uploading a backup file."""
    await setup_backup_integration(hass)

    client = await hass_client()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_receive_backup",
        return_value=TEST_BACKUP_ABC123.backup_id,
    ) as async_receive_backup_mock:
        resp = await client.post(
            "/api/backup/upload?agent_id=backup.local",
            data={"file": StringIO("test")},
        )
        assert resp.status == 201
        assert await resp.json() == {"backup_id": TEST_BACKUP_ABC123.backup_id}
        assert async_receive_backup_mock.called


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (OSError("Boom!"), "Can't write backup file: Boom!"),
        (asyncio.CancelledError("Boom!"), ""),
    ],
)
async def test_error_handling_uploading_a_backup_file(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    error: Exception,
    message: str,
) -> None:
    """Test error handling when uploading a backup file."""
    await setup_backup_integration(hass)

    client = await hass_client()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_receive_backup",
        side_effect=error,
    ):
        resp = await client.post(
            "/api/backup/upload?agent_id=backup.local",
            data={"file": StringIO("test")},
        )
        assert resp.status == 500
        assert await resp.text() == message
