"""Test the backups for OneDrive."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from io import StringIO
from unittest.mock import Mock, patch

from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    HashMismatchError,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import File
import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.onedrive.backup import (
    async_register_backup_agents_listener,
)
from homeassistant.components.onedrive.const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import BACKUP_METADATA

from tests.common import AsyncMock, MockConfigEntry
from tests.typing import ClientSessionGenerator, MagicMock, WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up onedrive and backup integrations."""
    async_initialize_backup(hass)
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
        await setup_integration(hass, mock_config_entry)

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
                "agent_id": f"{DOMAIN}.{mock_config_entry.unique_id}",
                "name": mock_config_entry.title,
            },
        ],
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
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
                "onedrive.mock_drive_id": {"protected": False, "size": 34519040}
            },
            "backup_id": "23e64aec",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "extra_metadata": {},
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        }
    ]


async def test_agents_list_backups_with_download_failure(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test agent list backups still works if one of the items fails to download."""
    mock_onedrive_client.download_drive_item.side_effect = OneDriveException("test")
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == []


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
            f"{DOMAIN}.{mock_config_entry.unique_id}": {
                "protected": False,
                "size": 34519040,
            }
        },
        "backup_id": "23e64aec",
        "date": "2024-11-22T11:48:48.727189+01:00",
        "database_included": True,
        "extra_metadata": {},
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2024.12.0.dev0",
        "name": "Core 2024.12.0.dev0",
        "failed_agent_ids": [],
        "with_automatic_settings": None,
    }


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onedrive_client: MagicMock,
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
    assert mock_onedrive_client.delete_drive_item.call_count == 2


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_onedrive_client: MagicMock,
    mock_large_file_upload_client: AsyncMock,
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
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    mock_large_file_upload_client.assert_called_once()
    mock_onedrive_client.update_drive_item.assert_called_once()


async def test_agents_upload_corrupt_upload(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_onedrive_client: MagicMock,
    mock_large_file_upload_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test hash validation fails."""
    mock_large_file_upload_client.side_effect = HashMismatchError("test")
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
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    mock_large_file_upload_client.assert_called_once()
    assert mock_onedrive_client.update_drive_item.call_count == 0
    assert "Hash validation failed, backup file might be corrupt" in caplog.text


async def test_agents_upload_metadata_upload_failed(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_onedrive_client: MagicMock,
    mock_large_file_upload_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test metadata upload fails."""
    client = await hass_client()
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)
    mock_onedrive_client.upload_file.side_effect = OneDriveException("test")

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
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    mock_large_file_upload_client.assert_called_once()
    mock_onedrive_client.delete_drive_item.assert_called_once()
    assert mock_onedrive_client.update_drive_item.call_count == 0


async def test_agents_upload_metadata_metadata_failed(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_onedrive_client: MagicMock,
    mock_large_file_upload_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test metadata upload on file description update."""
    client = await hass_client()
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)
    mock_onedrive_client.update_drive_item.side_effect = OneDriveException("test")

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
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    mock_large_file_upload_client.assert_called_once()
    assert mock_onedrive_client.update_drive_item.call_count == 1
    assert mock_onedrive_client.delete_drive_item.call_count == 2


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    backup_id = BACKUP_METADATA["backup_id"]

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.unique_id}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"


async def test_error_on_agents_download(
    hass_client: ClientSessionGenerator,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_backup_file: File,
    mock_metadata_file: File,
) -> None:
    """Test we get not found on an not existing backup on download."""
    client = await hass_client()
    backup_id = BACKUP_METADATA["backup_id"]
    mock_onedrive_client.list_drive_items.side_effect = [
        [mock_backup_file, mock_metadata_file],
        [],
    ]

    with patch("homeassistant.components.onedrive.backup.CACHE_TTL", -1):
        resp = await client.get(
            f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.unique_id}"
        )
    assert resp.status == 404


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (
            OneDriveException(),
            "Backup operation failed",
        ),
        (TimeoutError(), "Backup operation timed out"),
    ],
)
async def test_delete_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test error during delete."""
    mock_onedrive_client.delete_drive_item.side_effect = AsyncMock(
        side_effect=side_effect
    )

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
        "agent_errors": {f"{DOMAIN}.{mock_config_entry.unique_id}": error}
    }


async def test_agents_delete_not_found_does_not_throw(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test agent delete backup."""
    mock_onedrive_client.list_drive_items.return_value = []
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
    mock_onedrive_client: MagicMock,
) -> None:
    """Test backup not found."""

    mock_onedrive_client.list_drive_items.return_value = []
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] is None


async def test_reauth_on_403(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we re-authenticate on 403."""

    mock_onedrive_client.list_drive_items.side_effect = AuthenticationError(
        403, "Auth failed"
    )
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{mock_config_entry.unique_id}": "Authentication error"
    }

    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    # make sure it's the last listener
    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]
    remove_listener()

    assert hass.data.get(DATA_BACKUP_AGENT_LISTENERS) is None
