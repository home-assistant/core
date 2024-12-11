"""Test supervisor backup functionality."""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from io import StringIO
import os
from typing import Any
from unittest.mock import AsyncMock, patch

from aiohasupervisor.models import backups as supervisor_backups
import pytest

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
    Folder,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.typing import ClientSessionGenerator, WebSocketGenerator

TEST_BACKUP = supervisor_backups.Backup(
    compressed=False,
    content=supervisor_backups.BackupContent(
        addons=["ssl"],
        folders=["share"],
        homeassistant=True,
    ),
    date=datetime.fromisoformat("1970-01-01T00:00:00Z"),
    location="local",
    name="Test",
    protected=False,
    size=1.0,
    slug="abc123",
    type=supervisor_backups.BackupType.PARTIAL,
)
TEST_BACKUP_DETAILS = supervisor_backups.BackupComplete(
    addons=[
        supervisor_backups.BackupAddon(
            name="Terminal & SSH",
            size=0.0,
            slug="core_ssh",
            version="9.14.0",
        )
    ],
    compressed=TEST_BACKUP.compressed,
    date=TEST_BACKUP.date,
    folders=["share"],
    homeassistant_exclude_database=False,
    homeassistant="2024.12.0",
    location=TEST_BACKUP.location,
    name=TEST_BACKUP.name,
    protected=TEST_BACKUP.protected,
    repositories=[],
    size=TEST_BACKUP.size,
    slug=TEST_BACKUP.slug,
    supervisor_version="2024.11.2",
    type=TEST_BACKUP.type,
)


@pytest.fixture(autouse=True)
def fixture_supervisor_environ() -> Generator[None]:
    """Mock os environ for supervisor."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        yield


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> AsyncGenerator[None]:
    """Set up Backup integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=True),
        patch("homeassistant.components.backup.backup.is_hassio", return_value=True),
    ):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
        await hass.async_block_till_done()
        yield


@pytest.mark.usefixtures("hassio_client")
async def test_agent_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup agent info."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [{"agent_id": "hassio.local"}],
        "syncing": False,
    }


@pytest.mark.usefixtures("hassio_client")
async def test_agent_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent list backups."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.list.return_value = [TEST_BACKUP]
    supervisor_client.backups.backup_info.return_value = TEST_BACKUP_DETAILS

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == [
        {
            "addons": [
                {"name": "Terminal & SSH", "slug": "core_ssh", "version": "9.14.0"}
            ],
            "agent_ids": ["hassio.local"],
            "backup_id": "abc123",
            "database_included": True,
            "date": "1970-01-01T00:00:00+00:00",
            "folders": ["share"],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Test",
            "protected": False,
            "size": 1048576,
        }
    ]


@pytest.mark.usefixtures("hassio_client")
async def test_agent_download(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent download backup."""
    client = await hass_ws_client(hass)
    backup_id = "abc123"

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "agent_id": "hassio.local",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "backup_agents_download"
    assert response["error"]["message"] == "Not yet supported by supervisor"


@pytest.mark.usefixtures("hassio_client")
async def test_agent_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    backup_id = "test-backup"
    test_backup = AgentBackup(
        addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
        backup_id=backup_id,
        database_included=True,
        date="1970-01-01T00:00:00.000Z",
        folders=[Folder.MEDIA, Folder.SHARE],
        homeassistant_included=True,
        homeassistant_version="2024.12.0",
        name="Test",
        protected=False,
        size=0.0,
    )

    supervisor_client.backups.reload.assert_not_called()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("shutil.copy"),
    ):
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=hassio.local",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    supervisor_client.backups.reload.assert_called_once()


@pytest.mark.usefixtures("hassio_client")
async def test_agent_delete_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test agent delete backup."""
    client = await hass_ws_client(hass)
    backup_id = "abc123"

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert response["error"]["message"] == "Unknown error"


@pytest.mark.usefixtures("hassio_client")
async def test_reader_writer_create(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test generating a backup."""
    client = await hass_ws_client(hass)

    supervisor_client.backups.partial_backup.return_value.job_id = "abc123"
    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["hassio.local"], "name": "Test"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"backup_job_id": "abc123"}

    supervisor_client.backups.partial_backup.assert_called_once_with(
        supervisor_backups.PartialBackupOptions(
            addons=None,
            background=True,
            compressed=True,
            folders=None,
            homeassistant_exclude_database=False,
            homeassistant=True,
            location=None,
            name="Test",
            password=None,
        )
    )


@pytest.mark.usefixtures("hassio_client")
async def test_reader_writer_restore(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test restoring a backup."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.list.return_value = [TEST_BACKUP]

    await client.send_json_auto_id(
        {"type": "backup/restore", "agent_id": "hassio.local", "backup_id": "abc123"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    supervisor_client.backups.partial_restore.assert_called_once_with(
        "abc123",
        supervisor_backups.PartialRestoreOptions(
            addons=None,
            background=True,
            folders=None,
            homeassistant=True,
            password=None,
        ),
    )


@pytest.mark.parametrize(
    ("parameters", "expected_error"),
    [
        (
            {"restore_database": False},
            "Cannot restore Home Assistant without database",
        ),
        (
            {"restore_homeassistant": False},
            "Cannot restore database without Home Assistant",
        ),
    ],
)
@pytest.mark.usefixtures("hassio_client")
async def test_reader_writer_restore_wrong_parameters(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    parameters: dict[str, Any],
    expected_error: str,
) -> None:
    """Test trigger restore."""
    client = await hass_ws_client(hass)
    supervisor_client.backups.list.return_value = [TEST_BACKUP]

    default_parameters = {
        "type": "backup/restore",
        "agent_id": "hassio.local",
        "backup_id": "abc123",
    }

    await client.send_json_auto_id(default_parameters | parameters)
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": expected_error,
    }
