"""Test the Google Drive backup platform."""

from io import StringIO
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientResponse
from google_drive_api.exceptions import GoogleDriveApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
)
from homeassistant.components.google_drive import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import mock_stream
from tests.typing import ClientSessionGenerator, WebSocketGenerator

FOLDER_ID = "google-folder-it"
TEST_USER_EMAIL = "testuser@domain.com"
CONFIG_ENTRY_TITLE = "Google Drive entry title"
TEST_AGENT_BACKUP = AgentBackup(
    addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
    backup_id="test-backup",
    database_included=True,
    date="2025-01-01T01:23:45.678Z",
    extra_metadata={
        "with_automatic_settings": False,
    },
    folders=[],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Test",
    protected=False,
    size=987,
)


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USER_EMAIL,
        title=CONFIG_ENTRY_TITLE,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": time.time() + 3600,
                "scope": "https://www.googleapis.com/auth/drive.file",
            },
        },
    )


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Set up Google Drive integration."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("client-id", "client-secret"),
        DOMAIN,
    )
    mock_api.list_files = AsyncMock(
        return_value={"files": [{"id": "HA folder ID", "name": "HA folder name"}]}
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


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
        "agents": [
            {"agent_id": "backup.local"},
            {"agent_id": f"google_drive.{CONFIG_ENTRY_TITLE}"},
        ],
    }

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agents": [{"agent_id": "backup.local"}]}


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent list backups."""
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]
        }
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        TEST_AGENT_BACKUP.as_frontend_json()
        | {
            "agent_ids": [f"google_drive.{CONFIG_ENTRY_TITLE}"],
            "failed_agent_ids": [],
            "with_automatic_settings": None,
        }
    ]
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_list_backups_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent list backups fails."""
    mock_api.list_files = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {
            f"google_drive.{CONFIG_ENTRY_TITLE}": "Failed to list backups"
        },
        "backups": [],
        "last_attempted_automatic_backup": None,
        "last_completed_automatic_backup": None,
    }


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (
            TEST_AGENT_BACKUP.backup_id,
            TEST_AGENT_BACKUP.as_frontend_json()
            | {
                "agent_ids": [f"google_drive.{CONFIG_ENTRY_TITLE}"],
                "failed_agent_ids": [],
                "with_automatic_settings": None,
            },
        ),
        (
            "12345",
            None,
        ),
    ],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    backup_id: str,
    expected_result: dict[str, Any] | None,
) -> None:
    """Test agent get backup."""
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]
        }
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == expected_result


async def test_agents_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent download backup."""
    mock_api.list_files = AsyncMock(
        side_effect=[
            {"files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]},
            {"files": [{"id": "backup-file-id"}]},
        ]
    )
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.content = mock_stream(b"backup data")
    mock_api.get_file_content = AsyncMock(return_value=mock_response)

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id=google_drive.{CONFIG_ENTRY_TITLE}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"

    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_download_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent download backup fails."""
    mock_api.list_files = AsyncMock(
        side_effect=[
            {"files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]},
            {"files": [{"id": "backup-file-id"}]},
        ]
    )
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.content = mock_stream(b"backup data")
    mock_api.get_file_content = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id=google_drive.{CONFIG_ENTRY_TITLE}"
    )
    assert resp.status == 500
    content = await resp.content.read()
    assert "Failed to download backup" in content.decode()


async def test_agents_download_file_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent download backup raises error if not found."""
    mock_api.list_files = AsyncMock(
        side_effect=[
            {"files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]},
            {"files": []},
        ]
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id=google_drive.{CONFIG_ENTRY_TITLE}"
    )
    assert resp.status == 500
    content = await resp.content.read()
    assert "Backup not found" in content.decode()


async def test_agents_download_metadata_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent download backup raises error if not found."""
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]
        }
    )

    client = await hass_client()
    backup_id = "1234"
    assert backup_id != TEST_AGENT_BACKUP.backup_id

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id=google_drive.{CONFIG_ENTRY_TITLE}"
    )
    assert resp.status == 404
    assert await resp.content.read() == b""


async def test_agents_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = TEST_AGENT_BACKUP
        resp = await client.post(
            f"/api/backup/upload?agent_id=google_drive.{CONFIG_ENTRY_TITLE}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {TEST_AGENT_BACKUP.backup_id}" in caplog.text

    mock_api.upload_file.assert_called_once()
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_upload_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
) -> None:
    """Test agent upload backup fails."""
    mock_api.upload_file = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = TEST_AGENT_BACKUP
        resp = await client.post(
            f"/api/backup/upload?agent_id=google_drive.{CONFIG_ENTRY_TITLE}",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert "Upload backup error: some error" in caplog.text


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent delete backup."""
    mock_api.list_files = AsyncMock(return_value={"files": [{"id": "backup-file-id"}]})
    mock_api.delete_file = AsyncMock(return_value=None)

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

    mock_api.delete_file.assert_called_once()
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_delete_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent delete backup fails."""
    mock_api.list_files = AsyncMock(return_value={"files": [{"id": "backup-file-id"}]})
    mock_api.delete_file = AsyncMock(side_effect=GoogleDriveApiError("some error"))

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
        "agent_errors": {
            f"google_drive.{CONFIG_ENTRY_TITLE}": "Failed to delete backup"
        }
    }


async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent delete backup not found."""
    mock_api.list_files = AsyncMock(return_value={"files": []})

    client = await hass_ws_client(hass)
    backup_id = "1234"

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}

    mock_api.delete_file.assert_not_called()
