"""Test the backups for WebDAV."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from copy import deepcopy
from io import StringIO
from unittest.mock import Mock, patch

from aiowebdav2.exceptions import UnauthorizedError, WebDavError
import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.webdav.backup import async_register_backup_agents_listener
from homeassistant.components.webdav.const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_dumps
from homeassistant.setup import async_setup_component

from .const import BACKUP_METADATA

from tests.common import AsyncMock, MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, webdav_client: AsyncMock
) -> AsyncGenerator[None]:
    """Set up webdav integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        yield


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test backup agent info."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [
            {"agent_id": "backup.local", "name": "local"},
            {
                "agent_id": f"{DOMAIN}.{mock_config_entry.entry_id}",
                "name": mock_config_entry.title,
            },
        ],
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent list backups."""

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": [],
            "agents": {
                "webdav.01JKXV07ASC62D620DGYNG2R8H": {
                    "protected": False,
                    "size": 34519040,
                }
            },
            "backup_id": "23e64aec",
            "database_included": True,
            "date": "2025-02-10T17:47:22.727189+01:00",
            "extra_metadata": {},
            "failed_addons": [],
            "failed_agent_ids": [],
            "failed_folders": [],
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2025.2.1",
            "name": "Automatic backup 2025.2.1",
            "with_automatic_settings": None,
        }
    ]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent get backup."""

    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == {
        "addons": [],
        "agents": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": {
                "protected": False,
                "size": 34519040,
            }
        },
        "backup_id": "23e64aec",
        "database_included": True,
        "date": "2025-02-10T17:47:22.727189+01:00",
        "extra_metadata": {},
        "failed_addons": [],
        "failed_agent_ids": [],
        "failed_folders": [],
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2025.2.1",
        "name": "Automatic backup 2025.2.1",
        "with_automatic_settings": None,
    }


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    webdav_client: AsyncMock,
) -> None:
    """Test agent delete backup."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": BACKUP_METADATA["backup_id"],
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    assert webdav_client.clean.call_count == 2


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert webdav_client.upload_iter.call_count == 2


async def test_agents_upload_emits_progress_events(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_client: ClientSessionGenerator,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload emits progress events with bytes from upload_iter callbacks."""
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)
    client = await hass_client()
    ws_client = await hass_ws_client(hass)
    observed_progress_bytes: list[int] = []

    await ws_client.send_json_auto_id({"type": "backup/subscribe_events"})
    response = await ws_client.receive_json()
    assert response["event"] == {"manager_state": "idle"}
    response = await ws_client.receive_json()
    assert response["success"] is True

    async def _mock_upload_iter(*args: object, **kwargs: object) -> None:
        """Mock upload and trigger progress callback for backup upload."""
        path = args[1]
        if path.endswith(".tar"):
            progress = kwargs.get("progress")
            assert callable(progress)
            progress(1024, test_backup.size)
            progress(test_backup.size, test_backup.size)

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        webdav_client.upload_iter.side_effect = _mock_upload_iter
        fetch_backup.return_value = test_backup
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201

    # Gather progress events from the upload flow.
    reached_idle = False
    for _ in range(20):
        response = await ws_client.receive_json()
        event = response.get("event")

        if event is None:
            continue

        if (
            event.get("manager_state") == "receive_backup"
            and event.get("agent_id") == f"{DOMAIN}.{mock_config_entry.entry_id}"
            and "uploaded_bytes" in event
        ):
            observed_progress_bytes.append(event["uploaded_bytes"])

        if event == {"manager_state": "idle"}:
            reached_idle = True
            break

    assert reached_idle
    assert 1024 in observed_progress_bytes
    assert test_backup.size in observed_progress_bytes


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    backup_id = BACKUP_METADATA["backup_id"]

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"


async def test_error_on_agents_download(
    hass_client: ClientSessionGenerator,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we get not found on a not existing backup on download."""
    client = await hass_client()
    backup_id = BACKUP_METADATA["backup_id"]
    webdav_client.list_files.return_value = []

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 404


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (
            WebDavError("Unknown path"),
            "Backup operation failed: Unknown path",
        ),
        (TimeoutError(), "Backup operation timed out"),
    ],
)
async def test_delete_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test error during delete."""
    webdav_client.clean.side_effect = side_effect

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": BACKUP_METADATA["backup_id"],
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {f"{DOMAIN}.{mock_config_entry.entry_id}": error}
    }


async def test_agents_delete_not_found_does_not_throw(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    webdav_client: AsyncMock,
) -> None:
    """Test agent delete backup."""
    webdav_client.list_files.return_value = {}
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": BACKUP_METADATA["backup_id"],
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}


async def test_agents_backup_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    webdav_client: AsyncMock,
) -> None:
    """Test backup not found."""
    webdav_client.list_files.return_value = []
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] is None


async def test_raises_on_403(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we raise on 403."""
    webdav_client.list_files.side_effect = UnauthorizedError(
        "https://webdav.example.com"
    )
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{mock_config_entry.entry_id}": "Authentication error"
    }


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = AsyncMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    # make sure it's the last listener
    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]
    remove_listener()

    assert hass.data.get(DATA_BACKUP_AGENT_LISTENERS) is None


async def test_agents_list_backups_with_multi_chunk_metadata(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test listing backups when metadata is returned in multiple chunks."""
    metadata_json = json_dumps(BACKUP_METADATA).encode()
    mid = len(metadata_json) // 2
    chunk1 = metadata_json[:mid]
    chunk2 = metadata_json[mid:]

    async def _multi_chunk_download(path: str, timeout=None) -> AsyncIterator[bytes]:
        """Mock download returning metadata in multiple chunks."""
        if path.endswith(".json"):
            yield chunk1
            yield chunk2
            return
        yield b"backup data"

    webdav_client.download_iter.side_effect = _multi_chunk_download

    # Invalidate the metadata cache so the new mock is used
    hass.config_entries.async_update_entry(
        mock_config_entry, title=mock_config_entry.title
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    backups = response["result"]["backups"]
    assert len(backups) == 1
    assert backups[0]["backup_id"] == BACKUP_METADATA["backup_id"]
    assert backups[0]["name"] == BACKUP_METADATA["name"]


async def test_agents_list_backups_skips_invalid_metadata_file(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    webdav_client: AsyncMock,
) -> None:
    """Test listing backups skips unreadable metadata files."""
    broken_metadata_path = "/broken.metadata.json"
    valid_metadata_path = "/valid.metadata.json"
    valid_backup = deepcopy(BACKUP_METADATA)
    valid_backup["backup_id"] = "valid-backup"
    valid_backup["name"] = "Valid backup"

    webdav_client.list_files.return_value = [broken_metadata_path, valid_metadata_path]

    async def _download_metadata(path: str, timeout=None) -> AsyncIterator[bytes]:
        """Mock metadata downloads with one broken and one valid file."""
        if path == broken_metadata_path:
            yield b""
            return

        if path == valid_metadata_path:
            yield json_dumps(valid_backup).encode()
            return

        yield b"backup data"

    webdav_client.download_iter.side_effect = _download_metadata

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": [],
            "agents": {
                "webdav.01JKXV07ASC62D620DGYNG2R8H": {
                    "protected": False,
                    "size": 34519040,
                }
            },
            "backup_id": "valid-backup",
            "database_included": True,
            "date": "2025-02-10T17:47:22.727189+01:00",
            "extra_metadata": {},
            "failed_addons": [],
            "failed_agent_ids": [],
            "failed_folders": [],
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2025.2.1",
            "name": "Valid backup",
            "with_automatic_settings": None,
        }
    ]
