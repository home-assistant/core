"""Test Backblaze backup agent."""

from collections.abc import AsyncGenerator
import io
import json
import logging
from unittest.mock import MagicMock, Mock, patch

from b2sdk.v2.exception import B2Error
import pytest

from homeassistant.components.backblaze.backup import (
    BackblazeBackupAgent,
    async_get_backup_agents,
    async_register_backup_agents_listener,
    handle_b2_errors,
)
from homeassistant.components.backblaze.const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AgentBackup,
    BackupAgentError,
    BackupNotFound,
)
from homeassistant.core import HomeAssistant
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
            "failed_addons": [],
            "failed_agent_ids": [],
            "failed_folders": [],
            "with_automatic_settings": None,
        }
    ]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
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
                "protected": False,
                "size": 48,
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
    test_backup: AgentBackup,
) -> None:
    """Test agent download backup."""
    with patch("b2sdk.v2.FileVersion.download") as mock_download:
        # Mock the download of the main backup file
        mock_download.return_value.response.iter_content.return_value = iter(
            [b"backup data"]
        )

        # Mock the download of the metadata file
        # This mock is for when _find_file_and_metadata_name_by_id calls download() on the metadata file
        mock_download.return_value.text_content = json.dumps(BACKUP_METADATA)

        client = await hass_client()
        backup_id = TEST_BACKUP.backup_id

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


async def test_agents_upload_metadata_upload_fails(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent upload backup logs error if metadata upload fails."""
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
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent.async_upload_backup",
            side_effect=BackupAgentError("Failed during upload_files"),
        ),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = TEST_BACKUP
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": io.StringIO("test")},
        )

    assert resp.status == 201
    assert "Failed during upload_files" in caplog.text


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


async def test_agents_download_backup_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent download backup raises BackupNotFound."""
    with patch(
        "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_name_by_id",
        return_value=(None, None),
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


async def test_agents_delete_metadata_file_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent delete backup logs warning if metadata file not found."""
    with (
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_name_by_id",
            return_value=(Mock(file_name="test.tar"), "test.tar.metadata.json"),
        ),
        patch("b2sdk.v2.FileVersion.delete"),
        patch(
            "b2sdk._internal.raw_simulator.BucketSimulator.ls",
            return_value=[],
        ),
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
        assert (
            "Metadata file test.tar.metadata.json not found for deletion" in caplog.text
        )


async def test_agents_delete_metadata_file_b2_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent delete backup logs error if B2Error during metadata file deletion."""
    with (
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_name_by_id",
            return_value=(Mock(file_name="test.tar"), "test.tar.metadata.json"),
        ),
        patch("b2sdk.v2.FileVersion.delete"),
        patch(
            "b2sdk._internal.raw_simulator.BucketSimulator.ls",
            side_effect=B2Error("test b2 error"),
        ),
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
        assert (
            "Failed to delete metadata file test.tar.metadata.json: test b2 error"
            in caplog.text
        )


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [
        listener
    ]  # make sure it's the last listener
    remove_listener()

    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data


async def test_handle_b2_errors_decorator() -> None:
    """Test handle_b2_errors decorator."""

    @handle_b2_errors
    async def mock_func_raises_b2_error() -> None:
        raise B2Error("test error")

    with pytest.raises(
        BackupAgentError, match="Failed during mock_func_raises_b2_error"
    ):
        await mock_func_raises_b2_error()


async def test_async_download_backup_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_download_backup when backup is not found (line 106)."""
    with patch(
        "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_name_by_id",
        return_value=(None, None),
    ):
        client = await hass_client()
        backup_id = "non_existent_backup"

        resp = await client.get(
            f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
        )
        assert resp.status == 404


async def test_async_get_backup_metadata_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
) -> None:
    """Test async_get_backup when metadata file is not found (line 298)."""
    agents = await async_get_backup_agents(hass)
    agent = None
    for entry in agents:
        if (
            isinstance(entry, BackblazeBackupAgent)
            and entry.unique_id == mock_config_entry.entry_id
        ):
            agent = entry
            break

    if agent is None:
        pytest.fail("BackblazeBackupAgent not found")

    with (
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_name_by_id",
            return_value=(Mock(file_name="test.tar"), "test.tar.metadata.json"),
        ),
        patch(
            "b2sdk.v2.FileVersion.download",
            side_effect=BackupNotFound("Metadata file not found"),
        ),
        pytest.raises(BackupNotFound),
    ):
        await agent.async_get_backup(test_backup.backup_id)


async def test_process_metadata_file_for_id_sync_b2_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _process_metadata_file_for_id_sync with B2Error (lines 371-382)."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    file_name = "test.metadata.json"
    file_version = Mock()
    file_version.download.side_effect = B2Error("test error")

    with caplog.at_level(logging.WARNING):
        result = await hass.async_add_executor_job(
            agent._process_metadata_file_for_id_sync,
            file_name,
            file_version,
            "backup_id",
            {},
        )

        assert result == (None, None)
        assert "Failed to parse metadata file" in caplog.text


async def test_process_metadata_file_sync_b2_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _process_metadata_file_sync with B2Error (lines 441-451)."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    file_name = "test.metadata.json"
    file_version = Mock()
    file_version.download.side_effect = B2Error("test error")

    with caplog.at_level(logging.WARNING):
        result = await hass.async_add_executor_job(
            agent._process_metadata_file_sync,
            file_name,
            file_version,
            {},
        )

        assert result is None
        assert "Failed to parse metadata file" in caplog.text
