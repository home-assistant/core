"""Test the Backup SFTP Location platform."""

from io import StringIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.backup import AddonInfo, AgentBackup
from homeassistant.components.backup_sftp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_backup_integration  # noqa: F401
from .conftest import CONFIG_ENTRY_TITLE, TEST_AGENT_ID, AsyncFileIteratorMock

from tests.typing import ClientSessionGenerator, WebSocketGenerator

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
TEST_AGENT_BACKUP_RESULT = {
    "addons": [{"name": "Test", "slug": "test", "version": "1.0.0"}],
    "agents": {f"{DOMAIN}.{TEST_AGENT_ID}": {"protected": False, "size": 987}},
    "backup_id": "test-backup",
    "database_included": True,
    "date": "2025-01-01T01:23:45.678Z",
    "extra_metadata": {"with_automatic_settings": False},
    "folders": [],
    "homeassistant_included": True,
    "homeassistant_version": "2024.12.0",
    "name": "Test",
    "failed_agent_ids": [],
    "with_automatic_settings": None,
}


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
            {"agent_id": "backup.local", "name": "local"},
            {"agent_id": f"{DOMAIN}.{TEST_AGENT_ID}", "name": CONFIG_ENTRY_TITLE},
        ],
    }

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert (
        response["result"]
        == {"agents": [{"agent_id": "backup.local", "name": "local"}]}
        or config_entry.state == ConfigEntryState.NOT_LOADED
    )


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_list_backups(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent list backups."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [TEST_AGENT_BACKUP_RESULT]


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_list_backups_fail(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent list backups fails."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_list_backups.side_effect = RuntimeError("Error message")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == []
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{TEST_AGENT_ID}": "Failed to list backups: Error message"
    }


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (TEST_AGENT_BACKUP.backup_id, TEST_AGENT_BACKUP_RESULT),
        ("12345", None),
    ],
    ids=["found", "not_found"],
)
@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_get_backup(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_id: str,
    expected_result: dict[str, Any] | None,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent get backup."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] == expected_result


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_download(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent download backup."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.iter_file.return_value = AsyncFileIteratorMock(b"backup data")
    async_cm_mock.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_download_fail(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent download backup fails."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.iter_file = MagicMock(side_effect=RuntimeError("Error message."))
    async_cm_mock.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 500
    content = await resp.content.read()
    assert "Unexpected error while initiating download of backup" in content.decode()

    async_cm_mock.iter_file = MagicMock(side_effect=FileNotFoundError("Error message."))
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 500
    content = await resp.content.read()
    assert "Unable to initiate download of backup" in content.decode()


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_download_metadata_not_found(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent download backup raises error if not found."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_list_backups.return_value = []

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 404
    content = await resp.content.read()
    assert content.decode() == ""


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_upload(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent upload backup."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_upload_backup.return_value = None

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
            f"/api/backup/upload?agent_id={DOMAIN}.{TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup: {TEST_AGENT_BACKUP.backup_id}" in caplog.text
    assert (
        f"Successfully uploaded backup id: {TEST_AGENT_BACKUP.backup_id}" in caplog.text
    )

    async_cm_mock.async_upload_backup.assert_called_once()


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_upload_fail(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent upload backup fails."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_upload_backup = AsyncMock(
        side_effect=RuntimeError("Error message")
    )

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
            f"/api/backup/upload?agent_id={DOMAIN}.{TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert (
        "Failed to upload backup to remote SFTP location. Error: Error message"
        in caplog.text
    )


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_delete(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent delete backup."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_delete_backup.return_value = None

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

    async_cm_mock.async_delete_backup.assert_called_once()


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_delete_fail(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent delete backup fails."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_delete_backup.side_effect = AssertionError("Does not exist.")

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
            f"{DOMAIN}.{TEST_AGENT_ID}": "Failed to delete backup id: test-backup: Does not exist."
        }
    }

    # Test for unexpected exception
    async_cm_mock.async_delete_backup.side_effect = RuntimeError("Error Message.")
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()
    assert response["result"] == {
        "agent_errors": {
            f"{DOMAIN}.{TEST_AGENT_ID}": "Unexpected error while removing backup: test-backup: Error Message."
        }
    }


@patch("homeassistant.components.backup_sftp.backup.BackupAgentClient")
async def test_agents_delete_not_found(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    async_cm_mock: AsyncMock,
) -> None:
    """Test agent delete backup not found."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.async_list_backups.return_value = []

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

    async_cm_mock.async_delete_backup.assert_called_with(None)
