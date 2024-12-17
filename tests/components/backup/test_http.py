"""Tests for the Backup integration."""

import asyncio
from io import StringIO
from unittest.mock import patch

from aiohttp import web
import pytest

from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.core import HomeAssistant

from .common import TEST_BACKUP_ABC123, BackupAgentTest, setup_backup_integration

from tests.common import MockUser
from tests.typing import ClientSessionGenerator


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
    await setup_backup_integration(hass)
    hass.data[DATA_MANAGER].backup_agents["domain.test"] = BackupAgentTest("test")

    client = await hass_client()

    with (
        patch.object(BackupAgentTest, "async_download_backup") as download_mock,
    ):
        download_mock.return_value.__aiter__.return_value = iter((b"backup data",))
        resp = await client.get("/api/backup/download/abc123?agent_id=domain.test")
        assert resp.status == 200
        assert await resp.content.read() == b"backup data"


async def test_downloading_backup_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test downloading a backup file that does not exist."""
    await setup_backup_integration(hass)

    client = await hass_client()

    resp = await client.get("/api/backup/download/abc123?agent_id=backup.local")
    assert resp.status == 404


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
    ) as async_receive_backup_mock:
        resp = await client.post(
            "/api/backup/upload?agent_id=backup.local",
            data={"file": StringIO("test")},
        )
        assert resp.status == 201
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
