"""Backblaze B2 backup agent tests."""

from collections.abc import AsyncGenerator
from io import StringIO
import json
import logging
from time import time
from unittest.mock import Mock, patch

from b2sdk.v2.exception import B2Error
import pytest

from homeassistant.components.backblaze_b2.backup import (
    BackblazeBackupAgent,
    _parse_metadata,
    async_register_backup_agents_listener,
    suggested_filenames,
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


async def test_suggested_filenames() -> None:
    """Test filename generation from backup metadata."""
    tar_filename, metadata_filename = suggested_filenames(TEST_BACKUP)
    assert tar_filename.endswith(".tar")
    assert metadata_filename.endswith(".metadata.json")


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
    caplog: pytest.LogCaptureFixture,
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
    assert f"Uploading backup {TEST_BACKUP.backup_id}" in caplog.text


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


async def test_cache_expiration(agent: BackblazeBackupAgent) -> None:
    """Test cache expiration."""
    await agent.async_list_backups()
    await agent.async_list_backups()
    agent._backup_list_cache_expiration = time() - 1
    await agent.async_list_backups()


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


@pytest.mark.parametrize(
    ("error_type", "exception"),
    [("b2_error", B2Error)],
)
async def test_error_during_upload(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    agent: BackblazeBackupAgent,
    error_type: str,
    exception: type[Exception],
) -> None:
    """Test error handling during upload."""
    client = await hass_client()
    with patch.object(agent, "_bucket") as mock_bucket:
        mock_bucket.upload_bytes.side_effect = exception("Upload failed")
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )
        assert resp.status == 500


async def test_metadata_file_download_error(agent: BackblazeBackupAgent) -> None:
    """Test error during metadata file download."""
    with patch.object(agent, "_get_all_files_in_prefix") as mock_get_files:
        mock_metadata_file = Mock()
        mock_metadata_file.download.side_effect = B2Error("Download failed")
        mock_get_files.return_value = {
            "testprefix/backup123.metadata.json": mock_metadata_file
        }
        backups = await agent.async_list_backups()
        assert len(backups) == 0


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("async_delete_backup", ("nonexistent_backup",)),
        ("async_download_backup", ("nonexistent_backup",)),
    ],
)
async def test_backup_not_found_errors(
    agent: BackblazeBackupAgent, method: str, args: tuple
) -> None:
    """Test various backup not found scenarios."""
    with (
        patch.object(
            agent, "_find_file_and_metadata_version_by_id", return_value=(None, None)
        ),
        pytest.raises(BackupNotFound),
    ):
        await getattr(agent, method)(*args)


async def test_delete_metadata_with_b2_error(agent: BackblazeBackupAgent) -> None:
    """Test delete backup when metadata deletion fails with B2Error."""
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
        pytest.raises(BackupAgentError),
    ):
        await agent.async_delete_backup("test_backup")


async def test_upload_info_logs(
    agent: BackblazeBackupAgent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload backup generates info log messages."""

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


async def test_delete_backup_missing_metadata_with_warning(
    agent: BackblazeBackupAgent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test delete backup when metadata file is missing."""
    mock_main_file = Mock()
    mock_main_file.file_name = "backup.tar"
    with (
        patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            return_value=(mock_main_file, None),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await agent.async_delete_backup("test_backup")
        warning_logs = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("not found for deletion" in log for log in warning_logs)


async def test_async_get_backup_not_found(agent: BackblazeBackupAgent) -> None:
    """Test async_get_backup when backup is not found."""
    with (
        patch.object(agent, "async_list_backups", return_value=[]),
        pytest.raises(BackupNotFound),
    ):
        await agent.async_get_backup("nonexistent_backup")


@pytest.mark.parametrize(
    ("method", "patch_target", "args", "error_match"),
    [
        (
            "async_list_backups",
            "_get_all_files_in_prefix",
            (),
            "Failed during async_list_backups",
        ),
        (
            "async_get_backup",
            "_find_file_and_metadata_version_by_id",
            ("test_backup",),
            "Failed during async_get_backup",
        ),
    ],
)
async def test_b2_error_in_agent_methods(
    agent: BackblazeBackupAgent,
    method: str,
    patch_target: str,
    args: tuple,
    error_match: str,
) -> None:
    """Test B2Error during agent methods triggers error handler."""
    with (
        patch.object(agent, patch_target, side_effect=B2Error("API error")),
        pytest.raises(BackupAgentError, match=error_match),
    ):
        await getattr(agent, method)(*args)


async def test_upload_failure_cleanup(agent: BackblazeBackupAgent) -> None:
    """Test upload failure triggers cleanup."""

    async def mock_open_stream():
        return iter([b"test data"])

    with (
        patch.object(agent, "_bucket") as mock_bucket,
        patch.object(agent, "_cleanup_failed_upload") as mock_cleanup,
    ):
        mock_bucket.upload_unbound_stream.side_effect = B2Error("Upload failed")
        with pytest.raises(BackupAgentError):
            await agent.async_upload_backup(
                open_stream=mock_open_stream, backup=TEST_BACKUP
            )
        mock_cleanup.assert_called_once()


async def test_download_with_file_found(agent: BackblazeBackupAgent) -> None:
    """Test download with file found."""
    mock_file = Mock()
    mock_downloaded_file = Mock()
    mock_response = Mock()
    mock_response.iter_content.return_value = iter([b"backup data"])
    mock_downloaded_file.response = mock_response
    mock_file.download.return_value = mock_downloaded_file
    with patch.object(
        agent, "_find_file_and_metadata_version_by_id", return_value=(mock_file, None)
    ):
        async_iter = await agent.async_download_backup("test_backup")
        data = await anext(async_iter)
        assert data == b"backup data"


async def test_cache_return_from_get_backup(agent: BackblazeBackupAgent) -> None:
    """Test get_backup returns from cache when available."""
    agent._backup_list_cache = {TEST_BACKUP.backup_id: TEST_BACKUP}
    agent._backup_list_cache_expiration = time() + 300
    backup = await agent.async_get_backup(TEST_BACKUP.backup_id)
    assert backup == TEST_BACKUP


async def test_cleanup_file_delete_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful cleanup of failed upload."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    mock_file = Mock()
    with patch.object(agent, "_bucket") as mock_bucket:
        mock_bucket.get_file_info_by_name.return_value = mock_file
        await agent._cleanup_failed_upload("test_file.tar")
        mock_file.delete.assert_called_once()


async def test_small_upload_bytes_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test small backup uses upload_bytes path."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    async def mock_open_stream():
        return iter([b"small data"])

    with patch.object(agent, "_bucket") as mock_bucket:
        mock_bucket.upload_bytes.return_value = Mock(id_="small_id")
        await agent.async_upload_backup(
            open_stream=mock_open_stream, backup=TEST_BACKUP
        )
        mock_bucket.upload_bytes.assert_called()


async def test_cache_invalidation_with_file_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cache invalidation removes files from cache."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    agent._all_files_cache = {"test.tar": Mock(), "test.metadata.json": Mock()}
    agent._all_files_cache_expiration = time() + 300
    agent._backup_list_cache = {"backup123": Mock()}
    agent._backup_list_cache_expiration = time() + 300
    agent._invalidate_caches(
        "backup123", "test.tar", "test.metadata.json", remove_files=True
    )
    assert "test.tar" not in agent._all_files_cache
    assert "test.metadata.json" not in agent._all_files_cache
    assert "backup123" not in agent._backup_list_cache


async def test_cleanup_failed_upload_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling in cleanup failed upload."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    with (
        patch.object(agent, "_bucket") as mock_bucket,
        caplog.at_level(logging.WARNING),
    ):
        mock_bucket.get_file_info_by_name.side_effect = Exception("Unexpected error")
        await agent._cleanup_failed_upload("test_file.tar")
        warning_logs = [
            r.message for r in caplog.records if "Failed to clean up" in r.message
        ]
        assert len(warning_logs) > 0


async def test_metadata_processing_b2_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test B2Error during metadata processing."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    mock_file_version = Mock()
    mock_file_version.download.side_effect = B2Error("Download failed")
    with caplog.at_level(logging.WARNING):
        result = agent._process_metadata_file_for_id_sync(
            "b2error.metadata.json", mock_file_version, "target_backup_id", {}
        )
        assert result == (None, None)
        result2 = agent._process_metadata_file_sync(
            "b2error.metadata.json", mock_file_version, {}
        )
        assert result2 is None


async def test_get_backup_cache_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test get_backup updates cache when valid."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    agent._backup_list_cache = {}
    agent._backup_list_cache_expiration = time() + 300
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


def test_process_metadata_file_value_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test ValueError handling in metadata processing."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    mock_file = Mock()
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = b"invalid json"
    mock_download.response = mock_response
    mock_file.download.return_value = mock_download
    result = agent._process_metadata_file_for_id_sync(
        "test.metadata.json", mock_file, TEST_BACKUP.backup_id, {}
    )
    assert result == (None, None)


def test_process_metadata_file_no_backup_file(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test warning when metadata exists but no backup file."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    mock_file = Mock()
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps(BACKUP_METADATA).encode()
    mock_download.response = mock_response
    mock_file.download.return_value = mock_download
    all_files: dict[str, Mock] = {}
    result = agent._process_metadata_file_for_id_sync(
        "test.metadata.json", mock_file, TEST_BACKUP.backup_id, all_files
    )
    assert result == (None, None)


def test_process_single_metadata_value_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test ValueError in metadata file processing."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    mock_file = Mock()
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = b"invalid json"
    mock_download.response = mock_response
    mock_file.download.return_value = mock_download
    result = agent._process_metadata_file_sync("test.metadata.json", mock_file, {})
    assert result is None


def test_process_single_metadata_no_backup_file(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test warning when no backup file found."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    mock_file = Mock()
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps(BACKUP_METADATA).encode()
    mock_download.response = mock_response
    mock_file.download.return_value = mock_download
    all_files: dict[str, Mock] = {}
    result = agent._process_metadata_file_sync(
        "test.metadata.json", mock_file, all_files
    )
    assert result is None
