"""Test the Kitchen Sink backup platform."""

from collections.abc import AsyncGenerator
from io import StringIO
from unittest.mock import patch

import pytest

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
)
from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
async def backup_only() -> AsyncGenerator[None]:
    """Enable only the backup platform.

    The backup platform is not an entity platform.
    """
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Set up Kitchen Sink integration."""
    with patch("homeassistant.components.backup.is_hassio", return_value=False):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
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
        "agents": [{"agent_id": "backup.local"}, {"agent_id": "kitchen_sink.syncer"}],
        "syncing": False,
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test agent list backups."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/list_backups"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == [
        {
            "addons": [{"name": "Test", "slug": "test", "version": "1.0.0"}],
            "agent_id": "kitchen_sink.syncer",
            "backup_id": "abc123",
            "database_included": False,
            "date": "1970-01-01T00:00:00Z",
            "folders": ["media", "share"],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0",
            "name": "Kitchen sink syncer",
            "protected": False,
            "size": 1234,
        }
    ]


async def test_agents_download(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent download backup."""
    client = await hass_ws_client(hass)
    backup_id = "abc123"

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "agent_id": "kitchen_sink.syncer",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    path = hass.config.path(f"tmp_backups/{backup_id}.tar")
    assert f"Downloading backup {backup_id} to {path}" in caplog.text


async def test_agents_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    hass_supervisor_access_token: str,
) -> None:
    """Test agent upload backup."""
    ws_client = await hass_ws_client(hass, hass_supervisor_access_token)
    client = await hass_client()
    backup_id = "test-backup"
    test_backup = AgentBackup(
        addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
        backup_id=backup_id,
        database_included=True,
        date="1970-01-01T00:00:00.000Z",
        folders=["media", "share"],
        homeassistant_included=True,
        homeassistant_version="2024.12.0",
        name="Test",
        protected=False,
        size=0.0,
    )

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
    ):
        fetch_backup.return_value = test_backup
        resp = await client.post(
            "/api/backup/upload?agent_id=kitchen_sink.syncer",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    backup_name = f"{backup_id}.tar"
    assert f"Uploading backup {backup_name}" in caplog.text

    await ws_client.send_json_auto_id({"type": "backup/agents/list_backups"})
    response = await ws_client.receive_json()

    assert response["success"]
    backup_list = response["result"]
    assert len(backup_list) == 2
    assert backup_list[1] == {
        "addons": [{"name": "Test", "slug": "test", "version": "1.0.0"}],
        "agent_id": "kitchen_sink.syncer",
        "backup_id": "test-backup",
        "database_included": True,
        "date": "1970-01-01T00:00:00.000Z",
        "folders": ["media", "share"],
        "homeassistant_included": True,
        "homeassistant_version": "2024.12.0",
        "name": "Test",
        "protected": False,
        "size": 0.0,
    }


async def test_agent_delete_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
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

    assert response["success"]
    assert f"Deleted backup {backup_id}" in caplog.text

    await client.send_json_auto_id({"type": "backup/agents/list_backups"})
    response = await client.receive_json()

    assert response["success"]
    backup_list = response["result"]
    assert not backup_list
