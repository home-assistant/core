"""Test the backups for OneDrive."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from html import escape
from io import StringIO
from json import dumps
from unittest.mock import Mock, patch

from httpx import TimeoutException
from kiota_abstractions.api_error import APIError
from msgraph.generated.models.drive_item import DriveItem
from msgraph_core.models import LargeFileUploadSession
import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.onedrive.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
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
    """Set up onedrive integration."""
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
                "onedrive.mock_drive_id": {"protected": False, "size": 34519040}
            },
            "backup_id": "23e64aec",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        }
    ]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent get backup."""

    mock_drive_items.get = AsyncMock(
        return_value=DriveItem(description=escape(dumps(BACKUP_METADATA)))
    )
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
    mock_drive_items: MagicMock,
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
    mock_drive_items.delete.assert_called_once()


async def test_agents_delete_not_found_does_not_throw(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
) -> None:
    """Test agent delete backup."""
    mock_drive_items.children.get = AsyncMock(return_value=[])
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
    assert mock_drive_items.delete.call_count == 0


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_adapter: MagicMock,
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
        patch("homeassistant.components.onedrive.backup.UPLOAD_CHUNK_SIZE", 3),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    mock_drive_items.create_upload_session.post.assert_called_once()
    mock_drive_items.patch.assert_called_once()
    assert mock_adapter.send_async.call_count == 2
    assert mock_adapter.method_calls[0].args[0].content == b"tes"
    assert mock_adapter.method_calls[0].args[0].headers.get("Content-Range") == {
        "bytes 0-2/34519040"
    }
    assert mock_adapter.method_calls[1].args[0].content == b"t"
    assert mock_adapter.method_calls[1].args[0].headers.get("Content-Range") == {
        "bytes 3-3/34519040"
    }


async def test_broken_upload_session(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test broken upload session."""
    client = await hass_client()
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)

    mock_drive_items.create_upload_session.post = AsyncMock(return_value=None)

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
    assert "Failed to start backup upload" in caplog.text


@pytest.mark.parametrize(
    "side_effect",
    [
        APIError(response_status_code=500),
        TimeoutException("Timeout"),
    ],
)
async def test_agents_upload_errors_retried(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_adapter: MagicMock,
    side_effect: Exception,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)

    mock_adapter.send_async.side_effect = [
        side_effect,
        LargeFileUploadSession(next_expected_ranges=["2-"]),
        LargeFileUploadSession(next_expected_ranges=["2-"]),
    ]

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch("homeassistant.components.onedrive.backup.UPLOAD_CHUNK_SIZE", 3),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert mock_adapter.send_async.call_count == 3
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    mock_drive_items.patch.assert_called_once()


async def test_agents_upload_4xx_errors_not_retried(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_adapter: MagicMock,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)

    mock_adapter.send_async.side_effect = APIError(response_status_code=404)

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch("homeassistant.components.onedrive.backup.UPLOAD_CHUNK_SIZE", 3),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert mock_adapter.send_async.call_count == 1
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    assert mock_drive_items.patch.call_count == 0
    assert "Backup operation failed" in caplog.text


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIError(response_status_code=500), "Backup operation failed"),
        (TimeoutException("Timeout"), "Backup operation timed out"),
    ],
)
async def test_agents_upload_fails_after_max_retries(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_adapter: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    test_backup = AgentBackup.from_dict(BACKUP_METADATA)

    mock_adapter.send_async.side_effect = side_effect

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch("homeassistant.components.onedrive.backup.UPLOAD_CHUNK_SIZE", 3),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = test_backup
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.unique_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert mock_adapter.send_async.call_count == 6
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    assert mock_drive_items.patch.call_count == 0
    assert error in caplog.text


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent download backup."""
    mock_drive_items.get = AsyncMock(
        return_value=DriveItem(description=escape(dumps(BACKUP_METADATA)))
    )
    client = await hass_client()
    backup_id = BACKUP_METADATA["backup_id"]

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.unique_id}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
    mock_drive_items.content.get.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (
            APIError(response_status_code=500),
            "Backup operation failed",
        ),
        (TimeoutException("Timeout"), "Backup operation timed out"),
    ],
)
async def test_delete_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test error during delete."""
    mock_drive_items.delete = AsyncMock(side_effect=side_effect)

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


async def test_agents_backup_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
) -> None:
    """Test backup not found."""

    mock_drive_items.children.get = AsyncMock(return_value=[])
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] is None


async def test_reauth_on_403(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we re-authenticate on 403."""

    mock_drive_items.children.get = AsyncMock(
        side_effect=APIError(response_status_code=403)
    )
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{mock_config_entry.unique_id}": "Backup operation failed"
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
