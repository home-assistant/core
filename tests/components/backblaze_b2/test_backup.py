"""Backblaze B2 backup agent tests."""

from collections.abc import AsyncGenerator
from io import StringIO
import json
import logging
import time
from unittest.mock import AsyncMock, Mock, patch

from b2sdk.v2.exception import B2Error
import pytest

from homeassistant.components.backblaze_b2.backup import (
    BackblazeBackupAgent,
    _parse_metadata,
    async_register_backup_agents_listener,
)
from homeassistant.components.backblaze_b2.const import (
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    BackupAgentError,
    BackupNotFound,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import BACKUP_METADATA, TEST_BACKUP

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, MagicMock, WebSocketGenerator


@pytest.fixture
def agent(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> BackblazeBackupAgent:
    """Create a BackblazeBackupAgent instance."""
    return BackblazeBackupAgent(hass, mock_config_entry)


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up Backblaze B2 integration for backup tests."""
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
    assert any(
        agent["agent_id"] == f"{DOMAIN}.{mock_config_entry.entry_id}"
        for agent in response["result"]["agents"]
    )


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup listing."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()
    assert response["success"]
    assert "backups" in response["result"]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup retrieval."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
    )
    response = await client.receive_json()
    assert response["success"]
    if response["result"]["backup"]:
        assert response["result"]["backup"]["backup_id"] == TEST_BACKUP.backup_id


async def test_agents_get_backup_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup retrieval when backup not found."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": "random"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["backup"] is None


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup deletion."""
    client = await hass_ws_client(hass)
    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id"
    ) as mock_find:
        mock_main_file = Mock()
        mock_main_file.file_name = f"{TEST_BACKUP.backup_id}.tar"
        mock_metadata_file = Mock()
        mock_metadata_file.file_name = f"{TEST_BACKUP.backup_id}.metadata.json"
        mock_find.return_value = (mock_main_file, mock_metadata_file)
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == {"agent_errors": {}}


async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup deletion when backup not found."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/delete", "backup_id": "random"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agent_errors": {}}


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test backup upload."""
    client = await hass_client()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=TEST_BACKUP,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )
    assert resp.status == 201


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test backup download."""
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 200


async def test_agents_download_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test backup download when not found."""
    client = await hass_client()
    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
        return_value=(None, None),
    ):
        resp = await client.get(
            f"/api/backup/download/nonexistent?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
        )
        assert resp.status == 404


@pytest.mark.parametrize(
    ("error_type", "exception"),
    [
        ("b2_error", B2Error),
        ("runtime_error", RuntimeError),
    ],
)
async def test_error_during_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    error_type: str,
    exception: type[Exception],
) -> None:
    """Test error handling during backup deletion."""
    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent.async_delete_backup",
        side_effect=exception("Test error"),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()
    assert response["success"]
    assert (
        f"{DOMAIN}.{mock_config_entry.entry_id}" in response["result"]["agent_errors"]
    )


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener cleanup."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)
    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]  # type: ignore[misc]
    remove_listener()
    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data


async def test_parse_metadata_invalid_json() -> None:
    """Test metadata parsing with invalid JSON."""
    with pytest.raises(ValueError, match="Invalid JSON format"):
        _parse_metadata("invalid json")

    with pytest.raises(TypeError, match="JSON content is not a dictionary"):
        _parse_metadata('["not", "a", "dict"]')


async def test_error_during_list_and_get(agent: BackblazeBackupAgent) -> None:
    """Test error handling during list and get operations."""
    with (
        patch.object(
            agent, "_get_all_files_in_prefix", side_effect=B2Error("API error")
        ),
        pytest.raises(BackupAgentError, match="Failed during async_list_backups"),
    ):
        await agent.async_list_backups()

    with (
        patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            side_effect=B2Error("API error"),
        ),
        pytest.raises(BackupAgentError, match="Failed during async_get_backup"),
    ):
        await agent.async_get_backup("test_backup")


async def test_metadata_file_download_error(agent: BackblazeBackupAgent) -> None:
    """Test error during metadata file download."""
    mock_file_version = Mock()
    mock_file_version.download.side_effect = B2Error("Download failed")
    result = agent._process_metadata_file_sync(
        "error.metadata.json", mock_file_version, {}
    )
    assert result is None

    mock_file_version = Mock()
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = b"invalid json"
    mock_download.response = mock_response
    mock_file_version.download.return_value = mock_download
    result = agent._process_metadata_file_sync(
        "invalid.metadata.json", mock_file_version, {}
    )
    assert result is None


async def test_backup_file_not_found(agent: BackblazeBackupAgent) -> None:
    """Test scenarios where backup files are missing."""
    mock_file_version = Mock()
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps(BACKUP_METADATA).encode()
    mock_download.response = mock_response
    mock_file_version.download.return_value = mock_download

    all_files: dict[str, Mock] = {}
    result = agent._process_metadata_file_sync(
        "orphan.metadata.json", mock_file_version, all_files
    )
    assert result is None

    result2 = agent._process_metadata_file_for_id_sync(
        "orphan.metadata.json", mock_file_version, TEST_BACKUP.backup_id, all_files
    )
    assert result2 == (None, None)


async def test_backup_not_found_errors(agent: BackblazeBackupAgent) -> None:
    """Test various backup not found scenarios."""
    with (
        patch.object(agent, "async_list_backups", return_value=[]),
        pytest.raises(BackupNotFound),
    ):
        await agent.async_get_backup("nonexistent_backup")

    with (
        patch.object(
            agent, "_find_file_and_metadata_version_by_id", return_value=(None, None)
        ),
        pytest.raises(BackupNotFound),
    ):
        await agent.async_delete_backup("nonexistent_backup")

    with (
        patch.object(
            agent, "_find_file_and_metadata_version_by_id", return_value=(None, None)
        ),
        pytest.raises(BackupNotFound),
    ):
        await agent.async_download_backup("nonexistent_backup")


async def test_delete_backup_missing_metadata(agent: BackblazeBackupAgent) -> None:
    """Test delete backup when metadata file is missing."""
    mock_main_file = Mock()
    mock_main_file.file_name = "backup.tar"
    with patch.object(
        agent,
        "_find_file_and_metadata_version_by_id",
        return_value=(mock_main_file, None),
    ):
        await agent.async_delete_backup("test_backup")


async def test_error_during_delete_metadata(agent: BackblazeBackupAgent) -> None:
    """Test error during metadata file deletion."""
    mock_main_file = Mock()
    mock_metadata_file = Mock()
    mock_metadata_file.file_name = "backup.metadata.json"
    mock_metadata_file.delete.side_effect = B2Error("Delete failed")
    with (
        patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            return_value=(mock_main_file, mock_metadata_file),
        ),
        pytest.raises(BackupAgentError, match="Unexpected error in metadata deletion"),
    ):
        await agent.async_delete_backup("test_backup")


async def test_upload_success_and_cache_invalidation(
    agent: BackblazeBackupAgent,
) -> None:
    """Test successful upload with cache invalidation."""
    mock_stream = AsyncMock()
    mock_stream.__aiter__ = AsyncMock(return_value=iter([b"test_data"]))

    with (
        patch.object(agent, "_upload_backup_file") as mock_upload_backup,
        patch.object(agent, "_upload_metadata_file") as mock_upload_metadata,
        patch.object(agent, "_invalidate_caches") as mock_invalidate,
    ):
        await agent.async_upload_backup(
            open_stream=lambda: mock_stream,
            backup=TEST_BACKUP,
        )
        mock_upload_backup.assert_called_once()
        mock_upload_metadata.assert_called_once()
        mock_invalidate.assert_called_once()


async def test_cache_expiration(agent: BackblazeBackupAgent) -> None:
    """Test cache behavior for list and get operations."""
    agent._backup_list_cache = {TEST_BACKUP.backup_id: TEST_BACKUP}
    agent._backup_list_cache_expiration = time.time() + 300

    with patch.object(agent, "_get_all_files_in_prefix") as mock_get_files:
        backups = await agent.async_list_backups()
        assert len(backups) == 1
        assert backups[0].backup_id == TEST_BACKUP.backup_id
        mock_get_files.assert_not_called()

    with patch.object(agent, "_find_file_and_metadata_version_by_id") as mock_find:
        backup = await agent.async_get_backup(TEST_BACKUP.backup_id)
        assert backup.backup_id == TEST_BACKUP.backup_id
        mock_find.assert_not_called()


async def test_upload_with_logging(
    agent: BackblazeBackupAgent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload backup generates appropriate log messages."""

    async def mock_open_stream():
        return iter([b"test data"])

    with (
        patch.object(agent, "_bucket") as mock_bucket,
        caplog.at_level(logging.INFO),
    ):
        mock_bucket.upload_unbound_stream.return_value = Mock(id_="mock_id")
        mock_bucket.upload_bytes.return_value = Mock(id_="mock_metadata_id")
        await agent.async_upload_backup(
            open_stream=mock_open_stream, backup=TEST_BACKUP
        )
        info_logs = [r.message for r in caplog.records if r.levelname == "INFO"]
        assert any("Main backup file upload finished" in log for log in info_logs)
        assert any("Metadata file upload finished" in log for log in info_logs)


async def test_get_backup_with_cache_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test get_backup updates cache when backup is found."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    agent._backup_list_cache = {}
    agent._backup_list_cache_expiration = time.time() + 300
    mock_file = Mock()
    mock_metadata_file = Mock()
    mock_response = Mock()
    mock_response.content = b'{"test": "metadata"}'
    mock_download = Mock()
    mock_download.response = mock_response
    mock_metadata_file.download.return_value = mock_download
    with (
        patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            return_value=(mock_file, mock_metadata_file),
        ),
        patch(
            "homeassistant.components.backblaze_b2.backup._create_backup_from_metadata",
            return_value=TEST_BACKUP,
        ),
    ):
        result = await agent.async_get_backup(TEST_BACKUP.backup_id)
        assert TEST_BACKUP.backup_id in agent._backup_list_cache
        assert result == TEST_BACKUP


async def test_metadata_download_and_parsing_errors(
    agent: BackblazeBackupAgent,
) -> None:
    """Test metadata download and parsing error handling."""
    mock_file_version = Mock()
    mock_file_version.download.side_effect = B2Error("Download failed")

    result = agent._process_metadata_file_for_id_sync(
        "test.metadata.json", mock_file_version, TEST_BACKUP.backup_id, {}
    )
    assert result == (None, None)

    mock_file_version2 = Mock()
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = b"invalid json content"
    mock_download.response = mock_response
    mock_file_version2.download.return_value = mock_download

    result2 = agent._process_metadata_file_for_id_sync(
        "invalid.metadata.json", mock_file_version2, TEST_BACKUP.backup_id, {}
    )
    assert result2 == (None, None)


async def test_cache_invalidation_with_removal(agent: BackblazeBackupAgent) -> None:
    """Test cache invalidation with file removal."""
    mock_file1 = Mock()
    mock_file1.file_name = "test1.tar"
    mock_file2 = Mock()
    mock_file2.file_name = "test1.metadata.json"

    agent._all_files_cache = {
        "test1.tar": mock_file1,
        "test1.metadata.json": mock_file2,
    }
    agent._all_files_cache_expiration = time.time() + 300
    agent._backup_list_cache = {"backup1": TEST_BACKUP}
    agent._backup_list_cache_expiration = time.time() + 300

    agent._invalidate_caches(
        "backup1", "test1.tar", "test1.metadata.json", remove_files=True
    )
    assert "test1.tar" not in agent._all_files_cache
    assert "test1.metadata.json" not in agent._all_files_cache
    assert "backup1" not in agent._backup_list_cache

    agent._invalidate_caches(
        "backup2", "test2.tar", "test2.metadata.json", remove_files=False
    )
    assert agent._all_files_cache_expiration == 0.0
    assert agent._backup_list_cache_expiration == 0.0


async def test_upload_network_failure(
    agent: BackblazeBackupAgent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload failure with network error logging."""
    reader = AsyncMock()
    reader.__aiter__ = AsyncMock(return_value=iter([b"test"]))

    with (
        patch.object(
            agent._hass, "async_add_executor_job", side_effect=B2Error("Upload failed")
        ),
        pytest.raises(B2Error),
        caplog.at_level(logging.ERROR),
    ):
        await agent._upload_backup_file("error.tar", reader, {})

    error_logs = [r.message for r in caplog.records if r.levelname == "ERROR"]
    assert any(
        "B2 connection error during upload for error.tar" in log for log in error_logs
    )


async def test_upload_cleanup_on_failure(agent: BackblazeBackupAgent) -> None:
    """Test cleanup of main file when metadata upload fails."""

    async def mock_open_stream():
        return iter([b"test data"])

    with patch.object(agent, "_bucket") as mock_bucket:
        mock_file_info = Mock()
        mock_file_info.delete = Mock()
        mock_bucket.upload_unbound_stream.return_value = Mock(id_="main_id")
        mock_bucket.get_file_info_by_name.return_value = mock_file_info
        mock_bucket.upload_bytes.side_effect = B2Error("Metadata upload failed")

        with pytest.raises(BackupAgentError):
            await agent.async_upload_backup(
                open_stream=mock_open_stream, backup=TEST_BACKUP
            )

        mock_file_info.delete.assert_called_once()


async def test_semaphore_limits_concurrent_metadata_downloads(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that many backups can be listed without connection pool warnings."""
    client = await hass_ws_client(hass)

    # Create 15 mock metadata files to simulate many backups (more than default pool size of 10)
    mock_files = {}
    for i in range(15):
        mock_metadata = Mock()
        mock_metadata.file_name = f"testprefix/backup{i}.metadata.json"
        mock_download = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps(BACKUP_METADATA).encode()
        mock_download.response = mock_response
        mock_metadata.download.return_value = mock_download
        mock_files[f"testprefix/backup{i}.metadata.json"] = mock_metadata

        # Create corresponding tar file
        mock_tar = Mock(size=TEST_BACKUP.size)
        mock_tar.file_name = f"testprefix/backup{i}.tar"
        mock_files[f"testprefix/backup{i}.tar"] = mock_tar

    async def mock_get_all_files(_self):
        return mock_files

    with (
        patch(
            "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._get_all_files_in_prefix",
            mock_get_all_files,
        ),
        caplog.at_level(logging.WARNING),
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    # Verify no connection pool warnings appear (would contain "Connection pool is full")
    assert "Connection pool is full" not in caplog.text
