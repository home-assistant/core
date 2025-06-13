"""Test Backblaze backup agent."""

from collections.abc import AsyncGenerator
import io
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.backblaze.backup import (
    async_register_backup_agents_listener,
)
from homeassistant.components.backblaze.const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import BACKUP_METADATA, TEST_BACKUP

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up backblaze integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        async_initialize_backup(hass)
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
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
            "addons": TEST_BACKUP.addons,
            "backup_id": TEST_BACKUP.backup_id,
            "date": TEST_BACKUP.date,
            "database_included": TEST_BACKUP.database_included,
            "folders": TEST_BACKUP.folders,
            "homeassistant_included": TEST_BACKUP.homeassistant_included,
            "homeassistant_version": TEST_BACKUP.homeassistant_version,
            "name": TEST_BACKUP.name,
            "extra_metadata": TEST_BACKUP.extra_metadata,
            "agents": {
                f"{DOMAIN}.{mock_config_entry.entry_id}": {
                    "protected": TEST_BACKUP.protected,
                    "size": TEST_BACKUP.size,
                }
            },
            "failed_agent_ids": [],
            "with_automatic_settings": None,
            "failed_addons": [],
            "failed_folders": [],
        }
    ]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent get backup."""

    backup_id = TEST_BACKUP.backup_id
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == {
        "addons": [],
        "backup_id": backup_id,
        "date": TEST_BACKUP.date,
        "database_included": TEST_BACKUP.database_included,
        "folders": TEST_BACKUP.folders,
        "homeassistant_included": TEST_BACKUP.homeassistant_included,
        "homeassistant_version": TEST_BACKUP.homeassistant_version,
        "name": TEST_BACKUP.name,
        "extra_metadata": TEST_BACKUP.extra_metadata,
        "agents": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": {
                "protected": TEST_BACKUP.protected,
                "size": TEST_BACKUP.size,
            }
        },
        "failed_agent_ids": [],
        "with_automatic_settings": None,
        "failed_addons": [],
        "failed_folders": [],
    }


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent download backup."""
    with patch("b2sdk.v2.FileVersion.download", return_value=Mock()) as mock_download:

        def iter_content(chunk_size: int = 1) -> io.BytesIO:
            """Mock iter_content to return bytes."""
            return io.BytesIO(b"backup data")

        mock_download.return_value.response.iter_content = iter_content
        client = await hass_client()
        backup_id = BACKUP_METADATA["backup_id"]

        resp = await client.get(
            f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
        )
        assert resp.status == 200
        assert await resp.content.read() == b"backup data"


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = TEST_BACKUP
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": io.StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup {TEST_BACKUP.backup_id}" in caplog.text


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test agent delete backup."""
    with patch("b2sdk.v2.FileVersion.delete"):
        client = await hass_ws_client(hass)

        await client.send_json_auto_id(
            {
                "type": "backup/delete",
                "backup_id": TEST_BACKUP.backup_id,
            }
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}


async def test_agents_error_on_download_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent download backup."""
    with patch(
        "b2sdk._internal.raw_simulator.BucketSimulator.ls",
        return_value=[],
    ):
        client = await hass_client()
        backup_id = TEST_BACKUP.backup_id

        resp = await client.get(
            f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
        )
    assert resp.status == 404


async def test_agents_delete_not_throwing_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test agent delete backup does not throw on a backup not found."""
    with patch(
        "b2sdk._internal.raw_simulator.BucketSimulator.ls",
        return_value=[],
    ):
        client = await hass_ws_client(hass)

        await client.send_json_auto_id(
            {
                "type": "backup/delete",
                "backup_id": TEST_BACKUP.backup_id,
            }
        )
        response = await client.receive_json()

        assert response["success"]
        assert response["result"] == {"agent_errors": {}}


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [
        listener
    ]  # make sure it's the last listener
    remove_listener()

    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data
