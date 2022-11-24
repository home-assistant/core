"""Tests for the Backup integration."""
from collections.abc import Awaitable, Callable
from unittest.mock import patch

from aiohttp import ClientSession, web

from spencerassistant.core import spencerAssistant

from .common import TEST_BACKUP, setup_backup_integration

from tests.common import MockUser


async def test_downloading_backup(
    hass: spencerAssistant,
    hass_client: Callable[..., Awaitable[ClientSession]],
) -> None:
    """Test downloading a backup file."""
    await setup_backup_integration(hass)

    client = await hass_client()

    with patch(
        "spencerassistant.components.backup.http.BackupManager.get_backup",
        return_value=TEST_BACKUP,
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "spencerassistant.components.backup.http.FileResponse",
        return_value=web.Response(text=""),
    ):

        resp = await client.get("/api/backup/download/abc123")
        assert resp.status == 200


async def test_downloading_backup_not_found(
    hass: spencerAssistant,
    hass_client: Callable[..., Awaitable[ClientSession]],
) -> None:
    """Test downloading a backup file that does not exist."""
    await setup_backup_integration(hass)

    client = await hass_client()

    resp = await client.get("/api/backup/download/abc123")
    assert resp.status == 404


async def test_non_admin(
    hass: spencerAssistant,
    hass_client: Callable[..., Awaitable[ClientSession]],
    hass_admin_user: MockUser,
) -> None:
    """Test downloading a backup file that does not exist."""
    hass_admin_user.groups = []
    await setup_backup_integration(hass)

    client = await hass_client()

    resp = await client.get("/api/backup/download/abc123")
    assert resp.status == 401
