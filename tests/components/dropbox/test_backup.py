"""Test the Dropbox backup platform."""

from __future__ import annotations

from collections.abc import AsyncIterator
from io import StringIO
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from python_dropbox_api import DropboxAuthException

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
    suggested_filename,
)
from homeassistant.components.dropbox.backup import (
    DropboxFileOrFolderNotFoundException,
    DropboxUnknownException,
    async_register_backup_agents_listener,
)
from homeassistant.components.dropbox.const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
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


def _suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


async def _mock_metadata_stream(backup: AgentBackup) -> AsyncIterator[bytes]:
    """Create a mock metadata download stream."""
    yield json.dumps(backup.as_dict()).encode()


def _setup_list_folder_with_backup(
    mock_dropbox_client: Mock,
    backup: AgentBackup,
) -> None:
    """Set up mock to return a backup in list_folder and download_file."""
    tar_name, metadata_name = _suggested_filenames(backup)
    mock_dropbox_client.list_folder = AsyncMock(
        return_value=[
            SimpleNamespace(name=tar_name),
            SimpleNamespace(name=metadata_name),
        ]
    )
    mock_dropbox_client.download_file = Mock(return_value=_mock_metadata_stream(backup))


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dropbox_client,
) -> None:
    """Set up the Dropbox and Backup integrations for testing."""

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_dropbox_client.reset_mock()


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
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

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
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
    mock_dropbox_client: Mock,
) -> None:
    """Test listing backups via the Dropbox agent."""

    _setup_list_folder_with_backup(mock_dropbox_client, TEST_AGENT_BACKUP)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [TEST_AGENT_BACKUP_RESULT]
    mock_dropbox_client.list_folder.assert_awaited()


async def test_agents_list_backups_metadata_without_tar(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that orphaned metadata files are skipped with a warning."""

    mock_dropbox_client.list_folder = AsyncMock(
        return_value=[SimpleNamespace(name="orphan.metadata.json")]
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == []
    assert "without matching backup file" in caplog.text


async def test_agents_list_backups_invalid_metadata(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that invalid metadata files are skipped with a warning."""

    async def _invalid_stream() -> AsyncIterator[bytes]:
        yield b"not valid json"

    mock_dropbox_client.list_folder = AsyncMock(
        return_value=[
            SimpleNamespace(name="backup.tar"),
            SimpleNamespace(name="backup.metadata.json"),
        ]
    )
    mock_dropbox_client.download_file = Mock(return_value=_invalid_stream())

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == []
    assert "Skipping invalid metadata file" in caplog.text


async def test_agents_list_backups_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: Mock,
) -> None:
    """Test handling list backups failures."""

    mock_dropbox_client.list_folder = AsyncMock(
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


async def test_agents_list_backups_reauth(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication is triggered on auth error."""

    mock_dropbox_client.list_folder = AsyncMock(
        side_effect=DropboxAuthException("auth failed")
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == []
    assert response["result"]["agent_errors"] == {TEST_AGENT_ID: "Authentication error"}

    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    "backup_id",
    [TEST_AGENT_BACKUP.backup_id, "other-backup"],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: Mock,
    backup_id: str,
) -> None:
    """Test retrieving a backup's metadata."""

    _setup_list_folder_with_backup(mock_dropbox_client, TEST_AGENT_BACKUP)

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
    mock_dropbox_client: Mock,
) -> None:
    """Test downloading a backup file."""

    tar_name, metadata_name = _suggested_filenames(TEST_AGENT_BACKUP)

    mock_dropbox_client.list_folder = AsyncMock(
        return_value=[
            SimpleNamespace(name=tar_name),
            SimpleNamespace(name=metadata_name),
        ]
    )

    def download_side_effect(path: str) -> AsyncIterator[bytes]:
        if path == f"/{tar_name}":
            return mock_stream(b"backup data")
        return _mock_metadata_stream(TEST_AGENT_BACKUP)

    mock_dropbox_client.download_file = Mock(side_effect=download_side_effect)

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 200
    assert await resp.content.read() == b"backup data"


async def test_agents_download_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: Mock,
) -> None:
    """Test handling download failures."""

    mock_dropbox_client.list_folder = AsyncMock(
        side_effect=DropboxUnknownException("boom")
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 500
    body = await resp.content.read()
    assert b"Failed to get backup" in body


async def test_agents_download_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: Mock,
) -> None:
    """Test download when backup disappears between get and download."""

    tar_name, metadata_name = _suggested_filenames(TEST_AGENT_BACKUP)
    files = [
        SimpleNamespace(name=tar_name),
        SimpleNamespace(name=metadata_name),
    ]

    # First list_folder call (async_get_backup) returns the backup;
    # second call (async_download_backup) returns empty, simulating deletion.
    mock_dropbox_client.list_folder = AsyncMock(side_effect=[files, []])
    mock_dropbox_client.download_file = Mock(
        return_value=_mock_metadata_stream(TEST_AGENT_BACKUP)
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 404
    assert await resp.content.read() == b""


async def test_agents_download_file_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: Mock,
) -> None:
    """Test download when Dropbox file is not found returns 404."""

    mock_dropbox_client.list_folder = AsyncMock(
        side_effect=DropboxFileOrFolderNotFoundException("not found")
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )

    assert resp.status == 404


async def test_agents_download_metadata_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_dropbox_client: Mock,
) -> None:
    """Test download when metadata lookup fails."""

    mock_dropbox_client.list_folder = AsyncMock(return_value=[])

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
    mock_dropbox_client: Mock,
) -> None:
    """Test uploading a backup to Dropbox."""

    mock_dropbox_client.upload_file = AsyncMock(return_value=None)

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
    assert mock_dropbox_client.upload_file.await_count == 2


async def test_agents_upload_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_dropbox_client: Mock,
) -> None:
    """Test that backup tar is cleaned up when metadata upload fails."""

    call_count = 0

    async def upload_side_effect(path: str, stream: AsyncIterator[bytes]) -> None:
        nonlocal call_count
        call_count += 1
        async for _ in stream:
            pass
        if call_count == 2:
            raise DropboxUnknownException("metadata upload failed")

    mock_dropbox_client.upload_file = AsyncMock(side_effect=upload_side_effect)
    mock_dropbox_client.delete_file = AsyncMock()

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
    mock_dropbox_client.delete_file.assert_awaited_once()


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: Mock,
) -> None:
    """Test deleting a backup."""

    _setup_list_folder_with_backup(mock_dropbox_client, TEST_AGENT_BACKUP)
    mock_dropbox_client.delete_file = AsyncMock(return_value=None)

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
    assert mock_dropbox_client.delete_file.await_count == 2


async def test_agents_delete_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dropbox_client: Mock,
) -> None:
    """Test error handling when delete fails."""

    mock_dropbox_client.list_folder = AsyncMock(
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
    mock_dropbox_client: Mock,
) -> None:
    """Test deleting a backup that does not exist."""

    mock_dropbox_client.list_folder = AsyncMock(return_value=[])

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


async def test_remove_backup_agents_listener(
    hass: HomeAssistant,
) -> None:
    """Test removing a backup agent listener."""
    listener = Mock()
    remove = async_register_backup_agents_listener(hass, listener=listener)

    assert DATA_BACKUP_AGENT_LISTENERS in hass.data
    assert listener in hass.data[DATA_BACKUP_AGENT_LISTENERS]

    # Remove all other listeners to test the cleanup path
    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]

    remove()

    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data
