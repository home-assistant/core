"""Test the Dropbox backup platform."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
    BackupNotFound,
)
from homeassistant.components.dropbox.backup import DropboxUnknownException
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import CONFIG_ENTRY_TITLE, TEST_AGENT_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import mock_stream
from tests.typing import ClientSessionGenerator, WebSocketGenerator

TEST_AGENT_BACKUP = AgentBackup(
    addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
    backup_id="dropbox-backup",
    database_included=True,
    date="2025-01-01T00:00:00.000Z",
    extra_metadata={"with_automatic_settings": False},
    folders=[],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Dropbox backup",
    protected=False,
    size=2048,
)

TEST_AGENT_BACKUP_RESULT = {
    "addons": [{"name": "Test", "slug": "test", "version": "1.0.0"}],
    "agents": {TEST_AGENT_ID: {"protected": False, "size": 2048}},
    "backup_id": TEST_AGENT_BACKUP.backup_id,
    "database_included": True,
    "date": TEST_AGENT_BACKUP.date,
    "extra_metadata": {"with_automatic_settings": False},
    "failed_addons": [],
    "failed_agent_ids": [],
    "failed_folders": [],
    "folders": [],
    "homeassistant_included": True,
    "homeassistant_version": TEST_AGENT_BACKUP.homeassistant_version,
    "name": TEST_AGENT_BACKUP.name,
    "with_automatic_settings": None,
}


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_dropbox_client,
) -> None:
    """Set up the Dropbox and Backup integrations for testing."""

    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_dropbox_client.reset_mock()


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test listing available backup agents."""

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [
            {"agent_id": "backup.local", "name": "local"},
            {"agent_id": TEST_AGENT_ID, "name": CONFIG_ENTRY_TITLE},
        ]
    }

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [{"agent_id": "backup.local", "name": "local"}]
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test listing backups via the Dropbox agent."""

    mock_dropbox_client.async_list_backups = AsyncMock(return_value=[TEST_AGENT_BACKUP])

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [TEST_AGENT_BACKUP_RESULT]
    mock_dropbox_client.async_list_backups.assert_awaited()


async def test_agents_list_backups_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test handling list backups failures."""

    mock_dropbox_client.async_list_backups = AsyncMock(
        side_effect=DropboxUnknownException("boom")
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == []
    assert response["result"]["agent_errors"] == {
        TEST_AGENT_ID: "Failed to list backups"
    }


@pytest.mark.parametrize(
    "backup_id",
    [TEST_AGENT_BACKUP.backup_id, "other-backup"],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: AsyncMock,
    backup_id: str,
) -> None:
    """Test retrieving a backup's metadata."""

    mock_dropbox_client.async_list_backups = AsyncMock(return_value=[TEST_AGENT_BACKUP])

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    if backup_id == TEST_AGENT_BACKUP.backup_id:
        assert response["result"]["backup"] == TEST_AGENT_BACKUP_RESULT
    else:
        assert response["result"]["backup"] is None


async def test_agents_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test downloading a backup file."""

    mock_dropbox_client.async_list_backups = AsyncMock(return_value=[TEST_AGENT_BACKUP])
    mock_dropbox_client.async_download_backup = AsyncMock(
        return_value=mock_stream(b"backup data")
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
    mock_dropbox_client.async_download_backup.assert_awaited_once_with(
        TEST_AGENT_BACKUP.backup_id
    )


async def test_agents_download_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test handling download failures."""

    mock_dropbox_client.async_list_backups = AsyncMock(return_value=[TEST_AGENT_BACKUP])
    mock_dropbox_client.async_download_backup = AsyncMock(
        side_effect=DropboxUnknownException("boom")
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 500
    body = await resp.content.read()
    assert b"Failed to download backup" in body


async def test_agents_download_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test download when backup metadata is missing."""

    mock_dropbox_client.async_list_backups = AsyncMock(return_value=[TEST_AGENT_BACKUP])
    mock_dropbox_client.async_download_backup = AsyncMock(
        side_effect=BackupNotFound("missing")
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 404
    assert await resp.content.read() == b""


async def test_agents_download_metadata_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test download when metadata lookup fails."""

    mock_dropbox_client.async_list_backups = AsyncMock(return_value=[])

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 404
    assert await resp.content.read() == b""


async def test_agents_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test uploading a backup to Dropbox."""

    mock_dropbox_client.async_upload_backup = AsyncMock(return_value=None)

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {TEST_AGENT_BACKUP.backup_id} to agents" in caplog.text
    mock_dropbox_client.async_upload_backup.assert_awaited_once()


async def test_agents_upload_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test logging when upload fails."""

    mock_dropbox_client.async_upload_backup = AsyncMock(
        side_effect=DropboxUnknownException("boom")
    )

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert "Failed to upload backup" in caplog.text


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test deleting a backup."""

    mock_dropbox_client.async_delete_backup = AsyncMock(return_value=None)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    mock_dropbox_client.async_delete_backup.assert_awaited_once_with(
        TEST_AGENT_BACKUP.backup_id
    )


async def test_agents_delete_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test error handling when delete fails."""

    mock_dropbox_client.async_delete_backup = AsyncMock(
        side_effect=DropboxUnknownException("boom")
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {TEST_AGENT_ID: "Failed to delete backup"}
    }


async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test deleting a backup that does not exist."""

    mock_dropbox_client.async_delete_backup = AsyncMock(
        side_effect=BackupNotFound("missing")
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    mock_dropbox_client.async_delete_backup.assert_awaited_once_with(
        TEST_AGENT_BACKUP.backup_id
    )
