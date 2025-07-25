"""Test the Backup SFTP Location platform."""

from collections.abc import AsyncGenerator
from io import StringIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from asyncssh.sftp import SFTPError
import pytest

from homeassistant.components.backup import AddonInfo, AgentBackup
from homeassistant.components.backup_sftp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

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
    "failed_addons": [],
    "failed_agent_ids": [],
    "failed_folders": [],
    "folders": [],
    "homeassistant_included": True,
    "homeassistant_version": "2024.12.0",
    "name": "Test",
    "with_automatic_settings": None,
}


@pytest.fixture(autouse=True)
async def mock_setup_integration(
    setup_integration,
) -> None:
    """Set up the integration automatically for backup tests."""
    await setup_integration()


@pytest.fixture
async def backup_agent_client(async_cm_mock: AsyncMock) -> AsyncGenerator[AsyncMock]:
    """Fixture for mocking the BackupAgentClient."""
    with patch(
        "homeassistant.components.backup_sftp.backup.BackupAgentClient"
    ) as mock_client:
        mock_client.return_value = async_cm_mock
        yield async_cm_mock


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


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent list backups."""
    backup_agent_client.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [TEST_AGENT_BACKUP_RESULT]


async def test_agents_list_backups_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent list backups fails."""
    backup_agent_client.async_list_backups.side_effect = RuntimeError("Error message")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == []
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{TEST_AGENT_ID}": "Error message"
    }


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (TEST_AGENT_BACKUP.backup_id, TEST_AGENT_BACKUP_RESULT),
        ("12345", None),
    ],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_id: str,
    expected_result: dict[str, Any] | None,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent get backup."""
    backup_agent_client.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] == expected_result


async def test_agents_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent download backup."""
    backup_agent_client.iter_file.return_value = AsyncFileIteratorMock(b"backup data")
    backup_agent_client.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"


async def test_agents_download_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent download backup fails."""
    backup_agent_client.iter_file = MagicMock(
        side_effect=RuntimeError("Error message.")
    )
    backup_agent_client.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 500
    content = await resp.content.read()
    assert "Internal Server Error" in content.decode()

    backup_agent_client.iter_file = MagicMock(
        side_effect=FileNotFoundError("Error message.")
    )
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 404


async def test_agents_download_metadata_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent download backup raises error if not found."""
    backup_agent_client.async_list_backups.return_value = []

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 404
    content = await resp.content.read()
    assert content.decode() == ""


async def test_agents_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent upload backup."""
    backup_agent_client.async_upload_backup.return_value = None

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

    backup_agent_client.async_upload_backup.assert_called_once()


async def test_agents_upload_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent upload backup fails."""
    backup_agent_client.async_upload_backup = AsyncMock(
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
    assert "Error message" in caplog.text


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent delete backup."""
    backup_agent_client.async_delete_backup.return_value = None
    backup_agent_client.async_list_backups.return_value = [TEST_AGENT_BACKUP]

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

    backup_agent_client.async_delete_backup.assert_called_once()


@pytest.mark.parametrize(
    ("exc", "expected_result"),
    [
        (FileNotFoundError("Does not exist."), {"agent_errors": {}}),
        (
            SFTPError(0, "manual"),
            {
                "agent_errors": {
                    f"{DOMAIN}.{TEST_AGENT_ID}": f"Failed to delete backup id: {TEST_AGENT_BACKUP.backup_id}: manual"
                }
            },
        ),
        (
            RuntimeError("runtime error."),
            {"agent_errors": {f"{DOMAIN}.{TEST_AGENT_ID}": "runtime error."}},
        ),
    ],
    ids=["file_not_found_exc", "sftp_error_exc", "runtimer_error_exc"],
)
async def test_agents_delete_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_agent_client: AsyncMock,
    exc: Exception,
    expected_result: dict[str, dict[str, str]],
) -> None:
    """Test agent delete backup fails."""
    backup_agent_client.async_delete_backup.side_effect = exc
    backup_agent_client.async_list_backups.return_value = [TEST_AGENT_BACKUP]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == expected_result


async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_agent_client: AsyncMock,
) -> None:
    """Test agent delete backup not found."""
    backup_agent_client.async_list_backups.return_value = []

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

    backup_agent_client.async_delete_backup.assert_called_with(backup_id)
