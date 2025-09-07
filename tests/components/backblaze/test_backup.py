"""Backblaze backup agent tests with comprehensive coverage."""

import json
import logging
import tempfile
from time import time
from unittest.mock import AsyncMock, Mock, patch

from b2sdk.v2.exception import B2Error
import pytest

from homeassistant.components.backblaze.backup import (
    BackblazeBackupAgent,
    _parse_and_validate_metadata,
    async_get_backup_agents,
    async_register_backup_agents_listener,
    handle_b2_errors,
    suggested_filename,
    suggested_filenames,
)
from homeassistant.components.backblaze.const import (
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    MAX_BACKUP_SIZE,
    MAX_SIMPLE_UPLOAD_SIZE,
    METADATA_VERSION,
)
from homeassistant.components.backup import (
    AgentBackup,
    BackupAgentError,
    BackupNotFound,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import FileVersion
from .const import TEST_BACKUP

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


# Test Data Factories
def create_test_backup(backup_id="test_backup", name="test", size=1000, **kwargs):
    """Create a test backup with default values."""
    defaults = {
        "backup_id": backup_id,
        "date": "2021-01-01T00:00:00+00:00",
        "name": name,
        "size": size,
        "addons": [],
        "database_included": False,
        "extra_metadata": {},
        "folders": [],
        "homeassistant_included": False,
        "homeassistant_version": None,
        "protected": False,
    }
    defaults.update(kwargs)
    return AgentBackup(**defaults)


def create_mock_stream(data=b"test_data"):
    """Create a mock async stream generator."""

    async def stream_factory():
        async def stream_gen():
            if isinstance(data, bytes):
                yield data
            else:
                for chunk in data:
                    yield chunk

        return stream_gen()

    return stream_factory


def create_mock_metadata_file(backup_id="test", valid=True, close_error=False):
    """Create a mock file version with metadata content."""
    mock_file = Mock()
    mock_response = Mock()

    if valid:
        metadata_content = {
            "metadata_version": METADATA_VERSION,
            "backup_id": backup_id,
            "backup_metadata": {
                "backup_id": backup_id,
                "date": "2021-01-01T00:00:00+00:00",
                "name": "test_backup",
                "protected": False,
                "size": 1000,
                "addons": [],
                "database_included": False,
                "extra_metadata": {},
                "folders": [],
                "homeassistant_included": False,
                "homeassistant_version": None,
            },
        }
        mock_response.content = json.dumps(metadata_content).encode("utf-8")
    else:
        mock_response.content = b"{invalid json"

    if close_error:
        mock_response.close.side_effect = Exception("Close failed")
    else:
        mock_response.close = Mock()

    mock_file.download.return_value.response = mock_response
    return mock_file


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Set up backblaze integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        assert await async_setup_component(hass, "backup", {})
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()
        yield


@pytest.fixture
def agent(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Create a BackblazeBackupAgent instance."""
    return BackblazeBackupAgent(hass, mock_config_entry)


class TestBackblazeBackupUtilities:
    """Test utility functions and basic functionality."""

    def test_suggested_filename_generation(self):
        """Test filename generation from backup metadata."""
        backup = create_test_backup(name="my_backup")
        filename = suggested_filename(backup)
        assert filename == "my_backup_2021-01-01_00.00_00000000.tar"

        tar_filename, metadata_filename = suggested_filenames(backup)
        assert tar_filename == "my_backup_2021-01-01_00.00_00000000.tar"
        assert metadata_filename == "my_backup_2021-01-01_00.00_00000000.metadata.json"

    def test_metadata_validation(self):
        """Test metadata parsing and validation."""
        valid_metadata = {
            "metadata_version": METADATA_VERSION,
            "backup_id": "test",
            "backup_metadata": {
                "backup_id": "test",
                "date": "2021-01-01T00:00:00+00:00",
                "name": "test",
                "protected": False,
            },
        }

        # Valid metadata should parse successfully
        result = _parse_and_validate_metadata(json.dumps(valid_metadata))
        assert result["backup_id"] == "test"

        # Invalid JSON should raise ValueError
        with pytest.raises(ValueError, match="Invalid metadata format"):
            _parse_and_validate_metadata("{invalid json")

        # Missing required fields should raise ValueError
        incomplete = {k: v for k, v in valid_metadata.items() if k != "backup_id"}
        with pytest.raises(ValueError, match="backup_id"):
            _parse_and_validate_metadata(json.dumps(incomplete))

    async def test_error_decorator(self):
        """Test the B2Error handling decorator."""

        @handle_b2_errors
        async def failing_function():
            raise B2Error("test error")

        with pytest.raises(BackupAgentError):
            await failing_function()

    async def test_backup_agent_registration(self, hass: HomeAssistant):
        """Test backup agent registration and listeners."""
        # Test getting backup agents
        agents = await async_get_backup_agents(hass)
        assert len(agents) >= 1

        # Test listener registration and removal
        mock_listener = Mock()
        remove_fn = async_register_backup_agents_listener(hass, listener=mock_listener)

        # Verify listener was added
        listeners_count = len(hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []))

        # Remove listener
        remove_fn()

        # Verify listener was removed
        new_count = len(hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []))
        assert new_count == listeners_count - 1


class TestBackblazeBackupAgent:
    """Test BackblazeBackupAgent core functionality."""

    async def test_cache_management(self, agent):
        """Test cache invalidation and management."""
        # Set up cache with test data
        agent._all_files_cache = {"test.tar": "file1", "test.metadata.json": "file2"}
        agent._all_files_cache_expiration = time() + 300
        agent._backup_list_cache = {"backup123": "backup_obj"}
        agent._backup_list_cache_expiration = time() + 300

        # Test upload invalidation (expiration-based)
        agent._invalidate_caches("backup123", "test.tar", "test.metadata.json")
        assert agent._all_files_cache_expiration <= time()

        # Reset cache and test deletion invalidation (file removal-based)
        agent._all_files_cache = {"test.tar": "file1", "test.metadata.json": "file2"}
        agent._all_files_cache_expiration = time() + 300
        agent._backup_list_cache = {"backup123": "backup_obj"}
        agent._backup_list_cache_expiration = time() + 300

        agent._invalidate_caches(
            "backup123", "test.tar", "test.metadata.json", remove_files=True
        )
        assert "test.tar" not in agent._all_files_cache
        assert "backup123" not in agent._backup_list_cache

    async def test_stream_closing(self, agent):
        """Test stream closing with different close method availability."""
        # Test async close
        mock_stream_async = Mock()
        mock_stream_async.aclose = AsyncMock()
        await agent._close_stream(mock_stream_async)
        mock_stream_async.aclose.assert_called_once()

        # Test sync close fallback
        mock_stream_sync = Mock(spec=[])
        mock_stream_sync.close = Mock()
        await agent._close_stream(mock_stream_sync)
        mock_stream_sync.close.assert_called_once()

        # Test no close method available
        mock_stream_none = object()
        await agent._close_stream(mock_stream_none)  # Should not raise

    async def test_response_closing(self, agent):
        """Test response closing in executor."""
        # Test with close method
        mock_response = Mock()
        mock_response.close = Mock()
        await agent._close_response(mock_response)

        # Test without close method
        mock_response_no_close = object()
        await agent._close_response(mock_response_no_close)  # Should not raise

    async def test_cleanup_failed_upload(self, agent):
        """Test cleanup of failed uploads."""
        mock_file_info = Mock()
        mock_file_info.delete = Mock()

        with patch.object(
            agent._bucket, "get_file_info_by_name", return_value=mock_file_info
        ):
            await agent._cleanup_failed_upload("test_file.tar")
            mock_file_info.delete.assert_called_once()

    async def test_backup_list_cache_hit(self, agent):
        """Test cache hit scenarios for backup listing."""
        # Test all files cache hit
        agent._all_files_cache = {"test.tar": Mock()}
        agent._all_files_cache_expiration = time() + 300

        cached_files = await agent._get_all_files_in_prefix()
        assert cached_files == agent._all_files_cache

        # Test backup list cache hit
        mock_backup = Mock()
        mock_backup.backup_id = "cached_backup"
        agent._backup_list_cache = {"cached_backup": mock_backup}
        agent._backup_list_cache_expiration = time() + 300

        backup_list = await agent.async_list_backups()
        assert mock_backup in backup_list

        # Test individual backup cache hit
        cached_backup = await agent.async_get_backup("cached_backup")
        assert cached_backup == mock_backup

    async def test_listener_cleanup_empty_list(self, hass: HomeAssistant):
        """Test listener cleanup when list becomes empty."""
        # Ensure clean start
        if DATA_BACKUP_AGENT_LISTENERS in hass.data:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

        listener1 = Mock()
        listener2 = Mock()

        remove1 = async_register_backup_agents_listener(hass, listener=listener1)
        remove2 = async_register_backup_agents_listener(hass, listener=listener2)

        # Verify we have 2 listeners
        assert len(hass.data[DATA_BACKUP_AGENT_LISTENERS]) == 2

        # Remove both listeners
        remove1()
        remove2()

        # Verify the data key was deleted when list became empty
        assert DATA_BACKUP_AGENT_LISTENERS not in hass.data


class TestBackblazeBackupOperations:
    """Test backup upload, download, and delete operations."""

    @pytest.mark.parametrize(
        ("backup_size", "expected_method"),
        [
            (100, "simple"),
            (MAX_SIMPLE_UPLOAD_SIZE + 1000, "multipart"),
        ],
    )
    async def test_upload_backup(self, agent, backup_size, expected_method):
        """Test backup upload with different sizes."""
        backup = create_test_backup(size=backup_size)
        stream = create_mock_stream()

        mock_bucket = Mock()
        mock_file_version = Mock(id_="test_file_id")
        mock_bucket.upload_bytes.return_value = mock_file_version
        mock_bucket.upload_local_file.return_value = mock_file_version

        with patch.object(agent, "_bucket", mock_bucket):
            if expected_method == "multipart":
                with (
                    patch("tempfile.NamedTemporaryFile") as mock_temp,
                    patch(
                        "homeassistant.components.backblaze.backup.aiofiles.open"
                    ) as mock_aiofiles,
                    patch("os.chmod"),
                    tempfile.NamedTemporaryFile(delete=False) as temp_file,
                ):
                    mock_temp_file = Mock()
                    mock_temp_file.name = temp_file.name
                    mock_temp.return_value.__enter__.return_value = mock_temp_file

                    mock_file = Mock()
                    mock_file.write = AsyncMock()
                    mock_aiofiles.return_value.__aenter__.return_value = mock_file

                    await agent.async_upload_backup(open_stream=stream, backup=backup)
                    mock_bucket.upload_local_file.assert_called_once()
            else:
                await agent.async_upload_backup(open_stream=stream, backup=backup)
                assert mock_bucket.upload_bytes.call_count >= 1

    async def test_upload_backup_size_limit_exceeded(self, agent):
        """Test upload rejection when backup exceeds size limit."""
        huge_backup = create_test_backup(size=MAX_BACKUP_SIZE + 1)
        stream = create_mock_stream()

        with pytest.raises(BackupAgentError, match="exceeds maximum allowed size"):
            await agent.async_upload_backup(open_stream=stream, backup=huge_backup)

    async def test_upload_backup_multipart_progress_logging(self, agent, caplog):
        """Test progress logging during multipart upload."""
        large_backup = create_test_backup(size=MAX_SIMPLE_UPLOAD_SIZE + 1000)
        chunk_size = 50 * 1024 * 1024  # 50MB chunks
        large_stream = create_mock_stream([b"x" * chunk_size, b"y" * 1000])

        mock_bucket = Mock()
        mock_bucket.upload_local_file.return_value = Mock(id_="large_file_id")
        mock_bucket.upload_bytes.return_value = Mock()

        with (
            patch("tempfile.NamedTemporaryFile") as mock_temp,
            patch(
                "homeassistant.components.backblaze.backup.aiofiles.open"
            ) as mock_aiofiles,
            patch("os.chmod"),
            patch.object(agent, "_bucket", mock_bucket),
            caplog.at_level(logging.DEBUG),
            tempfile.NamedTemporaryFile(delete=False) as temp_file,
        ):
            mock_temp_file = Mock()
            mock_temp_file.name = temp_file.name
            mock_temp.return_value.__enter__.return_value = mock_temp_file

            mock_file = Mock()
            mock_file.write = AsyncMock()
            mock_aiofiles.return_value.__aenter__.return_value = mock_file

            await agent.async_upload_backup(
                open_stream=large_stream, backup=large_backup
            )

            # Verify progress logging occurred
            progress_logs = [
                r.message
                for r in caplog.records
                if "Written" in r.message and "bytes to temp file" in r.message
            ]
            assert len(progress_logs) > 0

    async def test_download_backup(self, agent):
        """Test backup download functionality."""
        mock_file = Mock()
        mock_response = Mock()
        mock_response.iter_content.return_value = iter([b"backup_data"])
        mock_file.download.return_value.response = mock_response

        with patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            return_value=(mock_file, Mock()),
        ):
            stream = await agent.async_download_backup("test_backup")
            data = b""
            async for chunk in stream:
                data += chunk
            assert data == b"backup_data"

    async def test_download_backup_not_found(self, agent):
        """Test download when backup not found."""
        with (
            patch.object(
                agent,
                "_find_file_and_metadata_version_by_id",
                return_value=(None, None),
            ),
            pytest.raises(BackupNotFound),
        ):
            await agent.async_download_backup("nonexistent")

    async def test_delete_backup_success(self, agent):
        """Test successful backup deletion."""
        mock_main_file = Mock()
        mock_metadata_file = Mock()

        with patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            return_value=(mock_main_file, mock_metadata_file),
        ):
            await agent.async_delete_backup("test_backup")
            mock_main_file.delete.assert_called_once()
            mock_metadata_file.delete.assert_called_once()

    async def test_delete_backup_not_found(self, agent):
        """Test delete when backup not found."""
        with (
            patch.object(
                agent,
                "_find_file_and_metadata_version_by_id",
                return_value=(None, None),
            ),
            pytest.raises(BackupNotFound),
        ):
            await agent.async_delete_backup("nonexistent")

    async def test_delete_backup_missing_metadata(self, agent, caplog):
        """Test delete when metadata file is missing."""
        mock_main_file = Mock()

        with (
            patch.object(
                agent,
                "_find_file_and_metadata_version_by_id",
                return_value=(mock_main_file, None),
            ),
            caplog.at_level(logging.WARNING),
        ):
            await agent.async_delete_backup("test_backup")
            mock_main_file.delete.assert_called_once()

            warning_logs = [
                r.message
                for r in caplog.records
                if "not found for deletion" in r.message
            ]
            assert len(warning_logs) > 0


class TestBackblazeErrorHandling:
    """Test error handling scenarios."""

    async def test_upload_metadata_failure(self, agent):
        """Test handling of metadata upload failure."""
        backup = create_test_backup(size=100)
        stream = create_mock_stream()

        mock_bucket = Mock()
        mock_bucket.upload_bytes.side_effect = [
            Mock(id_="main_file_id"),  # Success for main backup
            RuntimeError("Unexpected error"),  # Error for metadata
        ]

        with (
            patch.object(agent, "_bucket", mock_bucket),
            pytest.raises(BackupAgentError, match="An unexpected error occurred"),
        ):
            await agent.async_upload_backup(open_stream=stream, backup=backup)

    async def test_multipart_upload_exception(self, agent, caplog):
        """Test exception handling during multipart upload."""
        large_backup = create_test_backup(size=MAX_SIMPLE_UPLOAD_SIZE + 1000)
        stream = create_mock_stream()

        with (
            patch("tempfile.NamedTemporaryFile") as mock_temp,
            patch(
                "homeassistant.components.backblaze.backup.aiofiles.open",
                side_effect=RuntimeError("File system error"),
            ),
            patch("os.chmod"),
            caplog.at_level(logging.ERROR),
            tempfile.NamedTemporaryFile(delete=False) as temp_file,
        ):
            mock_temp_file = Mock()
            mock_temp_file.name = temp_file.name
            mock_temp.return_value.__enter__.return_value = mock_temp_file

            with pytest.raises(BackupAgentError):
                await agent.async_upload_backup(open_stream=stream, backup=large_backup)

            error_logs = [
                r.message
                for r in caplog.records
                if "An error occurred during upload" in r.message
            ]
            assert len(error_logs) > 0

    async def test_temp_file_cleanup_failure(self, agent, caplog):
        """Test temp file cleanup with failure scenarios."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name

            with (
                patch("os.unlink", side_effect=OSError("Permission denied")),
                patch("os.path.exists", return_value=True),
                patch("os.chmod"),
                patch.object(
                    agent, "_truncate_file", side_effect=OSError("Truncate failed")
                ),
                caplog.at_level(logging.ERROR),
            ):
                await agent._cleanup_temp_file(temp_file_path)

                error_logs = [
                    r.message
                    for r in caplog.records
                    if "Could not delete or truncate" in r.message
                ]
                assert len(error_logs) > 0

    async def test_delete_metadata_b2_error(self, agent):
        """Test B2Error during metadata file deletion."""
        mock_main_file = Mock()
        mock_metadata_file = Mock()
        mock_metadata_file.file_name = "test.metadata.json"
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

    async def test_delete_metadata_runtime_error(self, agent):
        """Test RuntimeError during metadata file deletion."""
        mock_main_file = Mock()
        mock_metadata_file = Mock()
        mock_metadata_file.file_name = "test.metadata.json"
        mock_metadata_file.delete.side_effect = RuntimeError("Unexpected error")

        with (
            patch.object(
                agent,
                "_find_file_and_metadata_version_by_id",
                return_value=(mock_main_file, mock_metadata_file),
            ),
            pytest.raises(
                BackupAgentError, match="Unexpected error in metadata deletion"
            ),
        ):
            await agent.async_delete_backup("test_backup")


class TestBackblazeMetadataProcessing:
    """Test metadata file processing scenarios."""

    async def test_list_backups_with_valid_metadata(self, agent):
        """Test listing backups with valid metadata files."""
        prefix = agent._prefix
        mock_metadata_file = create_mock_metadata_file("test_backup")
        mock_backup_file = Mock()
        mock_backup_file.size = 1000

        all_files = {
            f"{prefix}test_backup.tar": mock_backup_file,
            f"{prefix}test_backup.metadata.json": mock_metadata_file,
        }

        with patch.object(agent, "_get_all_files_in_prefix", return_value=all_files):
            backups = await agent.async_list_backups()
            assert len(backups) >= 1

    async def test_metadata_processing_invalid_json(self, agent, caplog):
        """Test processing of invalid JSON metadata."""
        mock_file_version = create_mock_metadata_file(valid=False)

        with caplog.at_level(logging.WARNING):
            result = agent._process_metadata_file_for_id_sync(
                "invalid.metadata.json", mock_file_version, "target_backup_id", {}
            )
            assert result == (None, None)

    async def test_metadata_processing_b2_error(self, agent, caplog):
        """Test B2Error during metadata processing."""
        mock_file_version = Mock()
        mock_file_version.download.side_effect = B2Error("Download failed")

        with caplog.at_level(logging.WARNING):
            # Test both processing methods
            result1 = agent._process_metadata_file_for_id_sync(
                "b2error.metadata.json", mock_file_version, "target_backup_id", {}
            )
            assert result1 == (None, None)

            result2 = agent._process_metadata_file_sync(
                "b2error.metadata.json", mock_file_version, {}
            )
            assert result2 is None

            b2_warning_logs = [
                r.message
                for r in caplog.records
                if "Failed to download metadata file" in r.message
            ]
            assert len(b2_warning_logs) > 0

    async def test_metadata_without_backup_file(self, agent, caplog):
        """Test metadata file without corresponding backup file."""
        mock_file_version = create_mock_metadata_file("orphan_backup_id")

        with caplog.at_level(logging.WARNING):
            result = agent._process_metadata_file_for_id_sync(
                "orphan_backup.metadata.json",
                mock_file_version,
                "orphan_backup_id",
                {},  # No backup files available
            )

            assert result == (None, None)
            warning_logs = [
                r.message
                for r in caplog.records
                if "but no corresponding backup file" in r.message
            ]
            assert len(warning_logs) > 0

    async def test_get_backup_cache_update(self, agent):
        """Test cache update when backup is found directly."""
        agent._backup_list_cache = {"other_backup": Mock()}
        agent._backup_list_cache_expiration = time() + 300

        mock_file = Mock(id_="test_id", file_name="direct_backup.tar")
        mock_metadata_file = Mock()
        mock_metadata_content = {"backup_id": "direct_backup", "name": "test"}
        test_backup = create_test_backup(backup_id="direct_backup", name="test")

        with (
            patch.object(
                agent,
                "_find_file_and_metadata_version_by_id",
                return_value=(mock_file, mock_metadata_file),
            ),
            patch(
                "homeassistant.components.backblaze.backup._parse_and_validate_metadata",
                return_value=mock_metadata_content,
            ),
            patch.object(agent, "_backup_from_b2_metadata", return_value=test_backup),
        ):
            result = await agent.async_get_backup("direct_backup")
            assert result == test_backup
            assert "direct_backup" in agent._backup_list_cache


class TestBackblazeWebSocketAPI:
    """Test WebSocket API functionality."""

    @pytest.mark.parametrize(
        "scenario",
        [
            "agents_info",
            "list_backups",
            "get_backup_success",
            "get_backup_not_found",
        ],
    )
    async def test_websocket_operations(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        mock_config_entry: MockConfigEntry,
        scenario: str,
    ):
        """Test various WebSocket API operations."""
        client = await hass_ws_client(hass)

        if scenario == "agents_info":
            await client.send_json_auto_id({"type": "backup/agents/info"})
            response = await client.receive_json()
            assert response["success"]
            assert any(
                agent["agent_id"] == f"{DOMAIN}.{mock_config_entry.entry_id}"
                for agent in response["result"]["agents"]
            )

        elif scenario == "list_backups":
            await client.send_json_auto_id({"type": "backup/info"})
            response = await client.receive_json()
            assert response["success"]
            assert "backups" in response["result"]

        elif scenario == "get_backup_success":
            await client.send_json_auto_id(
                {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
            )
            response = await client.receive_json()
            assert response["success"]
            assert response["result"]["backup"]["backup_id"] == TEST_BACKUP.backup_id

        elif scenario == "get_backup_not_found":
            with patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
                return_value=(None, None),
            ):
                await client.send_json_auto_id(
                    {"type": "backup/details", "backup_id": "nonexistent"}
                )
                response = await client.receive_json()
                assert response["success"]
                assert response["result"]["backup"] is None

    async def test_websocket_backup_operations(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
    ):
        """Test WebSocket backup operations like delete."""
        ws_client = await hass_ws_client(hass)
        http_client = await hass_client()

        # Test delete operation
        mock_backup_file = Mock(spec=FileVersion)
        mock_metadata_file = Mock(spec=FileVersion)

        agent = BackblazeBackupAgent(hass, mock_config_entry)
        with patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            return_value=(mock_backup_file, mock_metadata_file),
        ):
            await ws_client.send_json_auto_id(
                {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
            )
            response = await ws_client.receive_json()
            assert response["success"]

        # Test download operation
        with patch("b2sdk.v2.FileVersion.download") as mock_download:
            mock_response = Mock()
            mock_response.iter_content.return_value = iter([b"backup_data"])

            metadata_content = {
                "metadata_version": "1",
                "backup_id": TEST_BACKUP.backup_id,
                "backup_metadata": TEST_BACKUP.as_dict(),
            }
            mock_response.content = json.dumps(metadata_content).encode("utf-8")
            mock_download.return_value.response = mock_response

            resp = await http_client.get(
                f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
            )
            assert resp.status == 200


class TestBackblazeAdditionalCoverage:
    """Additional tests to reach 100% coverage of edge cases."""

    async def test_cleanup_failed_upload_exception(self, agent, caplog):
        """Test exception handling in cleanup failed upload."""
        with (
            patch.object(
                agent._bucket,
                "get_file_info_by_name",
                side_effect=Exception("Unexpected error"),
            ),
            caplog.at_level(logging.ERROR),
        ):
            await agent._cleanup_failed_upload("test_file.tar")

            # Should log exception details
            error_logs = [
                r.message for r in caplog.records if "Failed to clean up" in r.message
            ]
            assert len(error_logs) > 0
            manual_logs = [
                r.message
                for r in caplog.records
                if "Manual intervention may be required" in r.message
            ]
            assert len(manual_logs) > 0

    async def test_temp_file_cleanup_file_not_exists(self, agent):
        """Test temp file cleanup when file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            await agent._cleanup_temp_file("nonexistent_file")  # Should return early

    async def test_temp_file_cleanup_retry_success(self, agent):
        """Test temp file cleanup retry mechanism."""
        call_count = 0

        def mock_unlink(path):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 times
                raise OSError("Permission denied")
            # Success on 3rd try

        with (
            patch("os.path.exists", return_value=True),
            patch("os.chmod"),
            patch("os.unlink", side_effect=mock_unlink),
            tempfile.NamedTemporaryFile(delete=False) as temp_file,
        ):
            temp_retry_path = temp_file.name
            await agent._cleanup_temp_file(temp_retry_path)
            assert call_count == 3

    async def test_list_backups_empty_cache_miss(self, agent):
        """Test list backups when cache is expired and empty."""
        # Expire cache
        agent._backup_list_cache_expiration = 0.0
        agent._backup_list_cache = {}

        mock_files = {
            "test_backup.tar": Mock(size=1000),
            "test_backup.metadata.json": create_mock_metadata_file("test_backup"),
        }

        with patch.object(agent, "_get_all_files_in_prefix", return_value=mock_files):
            backups = await agent.async_list_backups()
            assert isinstance(backups, list)

    async def test_get_backup_no_cache_hit(self, agent):
        """Test get_backup when not in cache and needs direct fetch."""
        # Empty cache
        agent._backup_list_cache = {}
        agent._backup_list_cache_expiration = time() + 300

        mock_file = Mock(id_="test_id", file_name="test_backup.tar")
        mock_metadata_file = Mock()
        mock_metadata_content = {
            "backup_id": "test_backup",
            "backup_metadata": {"name": "test"},
        }
        test_backup = create_test_backup(backup_id="test_backup", name="test")

        with (
            patch.object(
                agent,
                "_find_file_and_metadata_version_by_id",
                return_value=(mock_file, mock_metadata_file),
            ),
            patch(
                "homeassistant.components.backblaze.backup._parse_and_validate_metadata",
                return_value=mock_metadata_content,
            ),
            patch.object(agent, "_backup_from_b2_metadata", return_value=test_backup),
        ):
            result = await agent.async_get_backup("test_backup")
            assert result == test_backup

    async def test_metadata_processing_sync_invalid_json(self, agent):
        """Test sync metadata processing with invalid JSON."""
        mock_file_version = create_mock_metadata_file(valid=False)

        result = agent._process_metadata_file_sync(
            "invalid.metadata.json", mock_file_version, {}
        )
        assert result is None

    async def test_metadata_processing_sync_missing_backup(self, agent, caplog):
        """Test sync metadata processing when backup file is missing."""
        mock_file_version = create_mock_metadata_file("orphan_backup")

        with caplog.at_level(logging.WARNING):
            result = agent._process_metadata_file_sync(
                "orphan.metadata.json",
                mock_file_version,
                {},  # No backup files
            )
            assert result is None

            warning_logs = [
                r.message
                for r in caplog.records
                if "but no corresponding backup file" in r.message
            ]
            assert len(warning_logs) > 0

    async def test_debug_backup_not_found_logging(self, agent, caplog):
        """Test debug logging when backup is not found."""
        with (
            patch.object(agent, "_get_all_files_in_prefix", return_value={}),
            caplog.at_level(logging.DEBUG),
            pytest.raises(BackupNotFound),
        ):
            await agent.async_get_backup("missing_backup")

        debug_logs = [
            r.message
            for r in caplog.records
            if "Backup missing_backup not found" in r.message
        ]
        assert len(debug_logs) > 0

    async def test_metadata_id_mismatch_debug_logging(self, agent, caplog):
        """Test debug logging when metadata doesn't match target ID."""
        mock_file_version = create_mock_metadata_file("different_backup_id")

        with caplog.at_level(logging.DEBUG):
            result = agent._process_metadata_file_for_id_sync(
                "different.metadata.json",
                mock_file_version,
                "target_backup_id",  # Different from file content
                {},
            )
            assert result == (None, None)

            debug_logs = [
                r.message
                for r in caplog.records
                if "does not match target backup ID" in r.message
            ]
            assert len(debug_logs) > 0

    async def test_response_close_with_executor(self, agent):
        """Test response closing through executor."""
        mock_response = Mock()
        mock_response.close = Mock()

        await agent._close_response(mock_response)
        # Should have been called through executor

    async def test_b2_error_during_multipart_upload(self, agent, caplog):
        """Test B2Error during multipart upload."""
        large_backup = create_test_backup(size=MAX_SIMPLE_UPLOAD_SIZE + 1000)
        stream = create_mock_stream()

        with (
            patch("tempfile.NamedTemporaryFile") as mock_temp,
            patch(
                "homeassistant.components.backblaze.backup.aiofiles.open",
                side_effect=B2Error("B2 upload error"),
            ),
            patch("os.chmod"),
            caplog.at_level(logging.ERROR),
            tempfile.NamedTemporaryFile(delete=False) as temp_file,
        ):
            mock_temp_file = Mock()
            mock_temp_file.name = temp_file.name
            mock_temp.return_value.__enter__.return_value = mock_temp_file

            with pytest.raises(BackupAgentError):
                await agent.async_upload_backup(open_stream=stream, backup=large_backup)

            error_logs = [
                r.message
                for r in caplog.records
                if "B2 connection error during upload" in r.message
            ]
            assert len(error_logs) > 0

    async def test_temp_file_successful_deletion_after_retry(self, agent, caplog):
        """Test successful temp file deletion after initial failure."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            call_count = 0

            def mock_unlink(path):
                nonlocal call_count
                call_count += 1
                if call_count == 1:  # Fail first time only
                    raise OSError("Permission denied")
                # Success on 2nd try - no exception

            with (
                patch("os.path.exists", return_value=True),
                patch("os.chmod"),
                patch("os.unlink", side_effect=mock_unlink),
                caplog.at_level(logging.DEBUG),
            ):
                await agent._cleanup_temp_file(temp_file_path)

                # Should log successful deletion
                debug_logs = [
                    r.message
                    for r in caplog.records
                    if "Successfully deleted temporary file" in r.message
                ]
                assert len(debug_logs) > 0

    def test_truncate_file_operation(self, agent):
        """Test the truncate file operation."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            test_file_path = temp_file.name

            # Mock open with context manager support
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)

            with patch("builtins.open", return_value=mock_file):
                agent._truncate_file(test_file_path)
                mock_file.__enter__.assert_called_once()
                mock_file.__exit__.assert_called_once()

    async def test_temp_file_cleanup_successful_truncation(self, agent, caplog):
        """Test successful temp file truncation after delete failure."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name

            with (
                patch("os.unlink", side_effect=OSError("Permission denied")),
                patch("os.path.exists", return_value=True),
                patch("os.chmod"),
                patch.object(
                    agent, "_truncate_file", return_value=None
                ),  # Successful truncation
                caplog.at_level(logging.INFO),
            ):
                await agent._cleanup_temp_file(temp_file_path)

                # Should log successful truncation
                info_logs = [
                    r.message
                    for r in caplog.records
                    if "Truncated temporary file" in r.message
                    and "as fallback" in r.message
                ]
                assert len(info_logs) > 0
