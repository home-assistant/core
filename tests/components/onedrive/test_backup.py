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
from syrupy.assertion import SnapshotAssertion

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
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent list backups."""

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == snapshot


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
    snapshot: SnapshotAssertion,
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
    assert response["result"]["backup"] == snapshot


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


async def test_broken_upload_session(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_upload_task: MagicMock,
    mock_drive_items: MagicMock,
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
            f"/api/backup/upload?agent_id={DOMAIN}.{DOMAIN}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert "Failed to start backup upload" in caplog.text


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
    """Test the error wrapper."""
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


@pytest.mark.parametrize(
    "problem",
    [
        AsyncMock(return_value=None),
        AsyncMock(side_effect=APIError(response_status_code=404)),
    ],
)
async def test_agents_backup_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
    problem: AsyncMock,
) -> None:
    """Test backup not found."""

    mock_drive_items.get = problem
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] is None


async def test_agents_backup_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
) -> None:
    """Test backup not found."""

    mock_drive_items.get = AsyncMock(side_effect=APIError(response_status_code=500))
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{DOMAIN}": "Failed to get backup"
    }


async def test_reauth_on_403(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_drive_items: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we re-authenticate on 403."""

    mock_drive_items.get = AsyncMock(side_effect=APIError(response_status_code=403))
    backup_id = BACKUP_METADATA["backup_id"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{DOMAIN}": "Failed to get backup"
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
