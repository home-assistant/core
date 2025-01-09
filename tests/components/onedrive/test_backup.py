"""Test the backups for OneDrive."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from html import escape
from io import StringIO
from json import dumps
from unittest.mock import Mock, patch

from kiota_abstractions.api_error import APIError
from msgraph.generated.models.drive_item import DriveItem
import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.onedrive.const import DOMAIN
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
    mock_graph_client: MagicMock,
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
) -> None:
    """Test backup agent info."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [{"agent_id": "backup.local"}, {"agent_id": f"{DOMAIN}.{DOMAIN}"}],
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_graph_client: MagicMock,
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
            "backup_id": "23e64aec",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "protected": False,
            "size": 34519040,
            "agent_ids": [f"{DOMAIN}.{DOMAIN}"],
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        }
    ]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
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
        "backup_id": "23e64aec",
        "date": "2024-11-22T11:48:48.727189+01:00",
        "database_included": True,
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2024.12.0.dev0",
        "name": "Core 2024.12.0.dev0",
        "protected": False,
        "size": 34519040,
        "agent_ids": [f"{DOMAIN}.{DOMAIN}"],
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


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_upload_task: MagicMock,
    mock_drive_items: MagicMock,
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
            f"/api/backup/upload?agent_id={DOMAIN}.{DOMAIN}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {test_backup.backup_id}" in caplog.text
    mock_drive_items.create_upload_session.post.assert_called_once()
    mock_drive_items.patch.assert_called_once()
    mock_upload_task.upload.assert_called_once()


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_drive_items: MagicMock,
) -> None:
    """Test agent download backup."""
    mock_drive_items.get = AsyncMock(
        return_value=DriveItem(description=escape(dumps(BACKUP_METADATA)))
    )
    client = await hass_client()
    backup_id = BACKUP_METADATA["backup_id"]

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{DOMAIN}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
    mock_drive_items.content.get.assert_called_once()


async def test_error_wrapper(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
) -> None:
    """Test agent delete backup."""
    mock_drive_items.delete = AsyncMock(
        side_effect=APIError(response_status_code=404, message="File not found.")
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
        "agent_errors": {f"{DOMAIN}.{DOMAIN}": "Failed to delete backup"}
    }
