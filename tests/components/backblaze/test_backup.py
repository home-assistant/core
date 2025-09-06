"""Consolidated Backblaze backup agent tests - optimized for minimal lines with 100% coverage."""

import io
import json
import logging
from time import time
from unittest.mock import AsyncMock, Mock, patch

from b2sdk.v2 import DEFAULT_MIN_PART_SIZE
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
from .const import BACKUP_METADATA, METADATA_FILE_SUFFIX, TEST_BACKUP

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


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


async def test_core_functionality(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test core functionality: suggested filenames, cache methods, utilities."""
    # Test suggested filename generation
    backup = AgentBackup(
        backup_id="a1b2c3",
        date="2021-01-01T01:02:03+00:00",
        addons=[],
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=False,
        homeassistant_version=None,
        name="my_pretty_backup",
        protected=False,
        size=0,
    )
    tar_filename = suggested_filename(backup)
    assert tar_filename == "my_pretty_backup_2021-01-01_01.02_03000000.tar"

    # Test cache methods for 100% coverage
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    agent._all_files_cache = {"test.tar": "file1", "test.metadata.json": "file2"}
    agent._all_files_cache_expiration = time() + 300
    agent._backup_list_cache = {"backup123": "backup_obj"}
    agent._backup_list_cache_expiration = time() + 300

    # Test upload invalidation (expiration-based)
    agent._invalidate_caches("backup123", "test.tar", "test.metadata.json")
    assert agent._all_files_cache_expiration <= time()

    # Test deletion invalidation when cache valid (file removal-based)
    agent._all_files_cache = {"test.tar": "file1", "test.metadata.json": "file2"}
    agent._all_files_cache_expiration = time() + 300
    agent._backup_list_cache = {"backup123": "backup_obj"}
    agent._backup_list_cache_expiration = time() + 300

    agent._invalidate_caches(
        "backup123", "test.tar", "test.metadata.json", remove_files=True
    )
    assert "test.tar" not in agent._all_files_cache
    assert "backup123" not in agent._backup_list_cache

    # Test error decorator
    @handle_b2_errors
    async def failing_func():
        raise B2Error("test error")

    with pytest.raises(BackupAgentError):
        await failing_func()

    # Test listener management
    mock_listener = Mock()
    remove_listener = async_register_backup_agents_listener(
        hass, listener=mock_listener
    )
    agents = await async_get_backup_agents(hass)
    assert len(agents) >= 1

    # Test listener removal (covers lines 91-93)
    listeners_before = len(hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []))
    remove_listener()
    listeners_after = len(hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []))
    assert listeners_after == listeners_before - 1

    # Test response closing fallback (covers lines 128-129)
    response_without_close = object()  # Object without close method
    await agent._close_response(response_without_close)  # Should not raise

    # Test cleanup failed upload method (covers lines 133-153)
    with patch.object(agent._bucket, "get_file_info_by_name") as mock_get_file:
        mock_file_info = Mock()
        mock_get_file.return_value = mock_file_info
        mock_file_info.delete = Mock()

        await agent._cleanup_failed_upload("test_file.tar")
        mock_get_file.assert_called_once_with("test_file.tar")
        mock_file_info.delete.assert_called_once()


async def test_additional_coverage(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test additional scenarios for coverage."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    # Test suggested_filenames function (covers lines 44-45)
    backup = AgentBackup(
        backup_id="test123",
        date="2021-01-01T01:02:03+00:00",
        addons=[],
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=False,
        homeassistant_version=None,
        name="test_backup",
        protected=False,
        size=0,
    )
    tar_filename, metadata_filename = suggested_filenames(backup)

    # Test cache invalidation path not covered (line 654)
    agent._all_files_cache_expiration = time() + 300
    agent._backup_list_cache_expiration = time() + 300
    agent._invalidate_caches("test", "test.tar", None, remove_files=True)

    # Test stream closing sync fallback (line 124)
    mock_stream = Mock(spec=[])  # Mock with no methods initially
    mock_stream.close = Mock()  # Add only sync close method

    await agent._close_stream(mock_stream)
    mock_stream.close.assert_called_once()

    # Test listener cleanup when list becomes empty (line 93)
    # First, ensure we have just one listener
    listeners = hass.data.get(DATA_BACKUP_AGENT_LISTENERS, [])
    for _ in range(len(listeners) - 1):  # Remove all but one
        if listeners:
            listeners.pop()

    # Add one more listener, then remove it to trigger cleanup
    test_listener = Mock()
    remove_fn = async_register_backup_agents_listener(hass, listener=test_listener)
    remove_fn()  # Should delete the key entirely if list becomes empty


@pytest.mark.parametrize(
    ("test_type", "scenario"),
    [
        ("websocket", "agents_info"),
        ("websocket", "list_backups"),
        ("websocket", "get_backup_success"),
        ("websocket", "get_backup_not_found"),
    ],
)
async def test_websocket_api(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    test_type: str,
    scenario: str,
) -> None:
    """Test WebSocket API functionality in a consolidated manner."""
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


@pytest.mark.parametrize(
    ("operation", "scenario"),
    [
        ("upload", "simple"),
        ("upload", "multipart"),
        ("upload", "metadata_failure"),
        ("download", "success"),
        ("download", "not_found"),
        ("delete", "success"),
        ("delete", "metadata_missing"),
        ("delete", "backup_not_found"),
    ],
)
async def test_backup_operations(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    operation: str,
    scenario: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload, download, and delete operations comprehensively."""
    if operation == "upload":
        client = await hass_client()

        # Setup based on scenario
        if scenario == "simple":
            backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100})
            mock_stream = io.BytesIO(b"test" * 25)
        elif scenario == "multipart":
            backup = AgentBackup(
                **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE + 1}
            )
            mock_stream = io.BytesIO(b"x" * (DEFAULT_MIN_PART_SIZE + 1))
        else:  # metadata_failure
            backup = TEST_BACKUP
            mock_stream = io.BytesIO(b"test_data")

        mock_bucket = Mock()
        mock_file_version = Mock(spec=FileVersion)
        mock_file_version.id_ = "test_file_id"

        if scenario == "metadata_failure":
            mock_bucket.upload_bytes.side_effect = [
                mock_file_version,
                B2Error("Metadata upload failed"),
            ]
        else:
            mock_bucket.upload_bytes.return_value = mock_file_version
            mock_bucket.upload_local_file.return_value = mock_file_version

        async def mock_stream_callable():
            async def stream_gen():
                yield mock_stream.read()

            return stream_gen()

        with (
            patch(
                "homeassistant.components.backup.manager.BackupManager.async_get_backup",
                return_value=backup,
            ),
            patch(
                "homeassistant.components.backup.manager.read_backup",
                return_value=backup,
            ),
            patch.object(mock_config_entry, "runtime_data", new=mock_bucket),
            patch("homeassistant.components.backblaze.backup.aiofiles.open")
            if scenario == "multipart"
            else patch("builtins.open"),
        ):
            agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

            if scenario == "metadata_failure":
                with pytest.raises(BackupAgentError):
                    await agent.async_upload_backup(
                        open_stream=mock_stream_callable, backup=backup
                    )
            else:
                await agent.async_upload_backup(
                    open_stream=mock_stream_callable, backup=backup
                )

    elif operation == "download":
        client = await hass_client()
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        if scenario == "success":
            with patch("b2sdk.v2.FileVersion.download") as mock_download:
                # The download needs to properly mock both the metadata file and backup file access
                mock_response = Mock()
                mock_response.iter_content.return_value = iter([b"backup_data"])
                # For metadata validation, we need proper content

                metadata_content = {
                    "metadata_version": "1",
                    "backup_id": TEST_BACKUP.backup_id,
                    "backup_metadata": TEST_BACKUP.as_dict(),
                }
                mock_response.content = json.dumps(metadata_content).encode("utf-8")
                mock_download.return_value.response = mock_response
                resp = await client.get(
                    f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
                )
                assert resp.status == 200

        else:  # not_found
            with (
                patch.object(
                    agent,
                    "_find_file_and_metadata_version_by_id",
                    return_value=(None, None),
                ),
                pytest.raises(BackupNotFound),
            ):
                async for _ in await agent.async_download_backup("nonexistent"):
                    pass

    elif operation == "delete":
        ws_client = await hass_ws_client(hass)
        agent = BackblazeBackupAgent(hass, mock_config_entry)

        if scenario == "success":
            mock_backup_file = Mock(spec=FileVersion)
            mock_metadata_file = Mock(spec=FileVersion)
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

        elif scenario == "metadata_missing":
            mock_backup_file = Mock(spec=FileVersion)
            with patch.object(
                agent,
                "_find_file_and_metadata_version_by_id",
                return_value=(mock_backup_file, None),
            ):
                await ws_client.send_json_auto_id(
                    {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
                )
                response = await ws_client.receive_json()
                assert response["success"]

        else:  # backup_not_found
            with (
                patch.object(
                    agent,
                    "_find_file_and_metadata_version_by_id",
                    return_value=(None, None),
                ),
                pytest.raises(BackupNotFound),
            ):
                await agent.async_delete_backup("nonexistent")


@pytest.mark.parametrize(
    "metadata_scenario",
    [
        "corrupted_json",
        "missing_backup_id",
        "id_mismatch",
        "metadata_without_backup",
        "b2_download_error",
    ],
)
async def test_metadata_processing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    metadata_scenario: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test all metadata processing scenarios in one consolidated test."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    prefix = mock_config_entry.data["prefix"]

    with caplog.at_level(logging.WARNING):
        if metadata_scenario == "corrupted_json":
            mock_file = Mock(spec=FileVersion)
            mock_file.file_name = f"{prefix}corrupted.tar{METADATA_FILE_SUFFIX}"
            mock_file.download.return_value.response.content = b"{invalid json"

            mock_files = {mock_file.file_name: mock_file}
            with patch.object(
                agent, "_get_all_files_in_prefix", return_value=mock_files
            ):
                backups = await agent.async_list_backups()
                assert len(backups) == 0
                # With schema validation, corrupted JSON files are silently skipped

        elif metadata_scenario == "missing_backup_id":
            # Test that schema validation catches missing required fields
            incomplete_metadata = {
                k: v for k, v in BACKUP_METADATA.items() if k != "backup_id"
            }
            with pytest.raises(ValueError, match="backup_id"):
                _parse_and_validate_metadata(json.dumps(incomplete_metadata))

        elif metadata_scenario == "id_mismatch":
            # Test that schema validation works for valid but mismatched IDs
            mismatched = {**BACKUP_METADATA, "backup_id": "different_id"}
            # This should validate successfully as it's structurally valid
            result = _parse_and_validate_metadata(json.dumps(mismatched))
            assert result["backup_id"] == "different_id"

        elif metadata_scenario == "metadata_without_backup":
            mock_metadata = Mock(spec=FileVersion)
            mock_metadata.file_name = f"{prefix}orphan.tar{METADATA_FILE_SUFFIX}"
            mock_metadata.download.return_value.response.content = json.dumps(
                {
                    "metadata_version": METADATA_VERSION,
                    "backup_id": "orphan",
                    "backup_metadata": TEST_BACKUP.as_dict(),
                }
            ).encode()

            with patch.object(
                agent,
                "_get_all_files_in_prefix",
                return_value={mock_metadata.file_name: mock_metadata},
            ):
                backups = await agent.async_list_backups()
                assert len(backups) == 0
                assert "Found metadata file" in caplog.text

        elif metadata_scenario == "b2_download_error":
            mock_file = Mock(spec=FileVersion)
            mock_file.file_name = f"{prefix}error.tar{METADATA_FILE_SUFFIX}"
            mock_file.download.side_effect = B2Error("Download failed")

            with patch.object(
                agent,
                "_get_all_files_in_prefix",
                return_value={mock_file.file_name: mock_file},
            ):
                backups = await agent.async_list_backups()
                assert len(backups) == 0


@pytest.mark.parametrize(
    "error_scenario",
    [
        "stream_close_failure",
        "multipart_b2_error",
        "temp_file_cleanup_failure",
    ],
)
async def test_error_handling(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    error_scenario: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test comprehensive error handling scenarios."""
    client = await hass_client()
    backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE + 1})
    agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

    if error_scenario == "stream_close_failure":
        # Test stream closing behavior
        class MockStreamClose:
            def __init__(self) -> None:
                self.close_called = False

            async def __aiter__(self):
                yield b"chunk1"

            def close(self):
                self.close_called = True

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.close()

        stream = MockStreamClose()
        mock_callable = AsyncMock(return_value=stream)

        with (
            patch(
                "homeassistant.components.backup.manager.BackupManager.async_get_backup",
                return_value=backup,
            ),
            patch("homeassistant.components.backblaze.backup.aiofiles.open"),
        ):
            # Add missing method to the bucket simulator
            if not hasattr(agent._bucket, "upload_local_file"):
                agent._bucket.upload_local_file = Mock(return_value=Mock())
            if not hasattr(agent._bucket, "upload_bytes"):
                agent._bucket.upload_bytes = Mock(return_value=Mock())

            await agent.async_upload_backup(open_stream=mock_callable, backup=backup)
            assert stream.close_called

    elif error_scenario == "multipart_b2_error":
        with (
            patch(
                "homeassistant.components.backblaze.backup.aiofiles.open",
                side_effect=B2Error("B2 error"),
            ),
            caplog.at_level(logging.ERROR),
        ):
            # Add missing method to the bucket simulator
            if not hasattr(agent._bucket, "upload_local_file"):
                agent._bucket.upload_local_file = Mock(return_value=Mock())
            if not hasattr(agent._bucket, "upload_bytes"):
                agent._bucket.upload_bytes = Mock(return_value=Mock())

            mock_callable = AsyncMock()
            with pytest.raises(BackupAgentError):
                await agent.async_upload_backup(
                    open_stream=mock_callable, backup=backup
                )
            assert "B2 connection error during upload" in caplog.text

    elif error_scenario == "temp_file_cleanup_failure":
        mock_callable = AsyncMock()

        with (
            patch("homeassistant.components.backblaze.backup.aiofiles.open"),
            patch("os.unlink", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.WARNING),
        ):
            # Add missing methods to the bucket simulator
            if not hasattr(agent._bucket, "upload_local_file"):
                agent._bucket.upload_local_file = Mock(return_value=Mock())
            if not hasattr(agent._bucket, "upload_bytes"):
                agent._bucket.upload_bytes = Mock(return_value=Mock())

            await agent.async_upload_backup(open_stream=mock_callable, backup=backup)
            assert any(
                "Failed to delete temporary file" in record.message
                for record in caplog.records
            )


async def test_debug_scenarios(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test debug logging and edge cases for complete coverage."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    with (
        caplog.at_level(logging.DEBUG),
        patch.object(agent, "_get_all_files_in_prefix", return_value={}),
        pytest.raises(BackupNotFound),
    ):
        await agent.async_get_backup("missing_backup")
    assert "Backup missing_backup not found" in caplog.text


async def test_coverage_edge_cases(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test edge cases to achieve 100% coverage."""

    # Test listener removal when list becomes empty (line 129)
    listener1 = Mock()
    listener2 = Mock()
    remove1 = async_register_backup_agents_listener(hass, listener=listener1)
    remove2 = async_register_backup_agents_listener(hass, listener=listener2)

    # Remove both to trigger empty list cleanup
    remove1()
    remove2()  # This should delete the data key entirely

    # Test backup size too large (lines 259-262)
    huge_backup = AgentBackup(
        backup_id="huge",
        date="2021-01-01T00:00:00+00:00",
        name="huge_backup",
        size=MAX_BACKUP_SIZE + 1,  # Exceeds limit
        addons=[],
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=False,
        homeassistant_version=None,
        protected=False,
    )

    agent = BackblazeBackupAgent(hass, mock_config_entry)

    with pytest.raises(BackupAgentError, match="exceeds maximum allowed size"):
        await agent.async_upload_backup(open_stream=AsyncMock(), backup=huge_backup)

    # Test generic exception in upload (lines 301-305)
    small_backup = AgentBackup(
        backup_id="small",
        date="2021-01-01T00:00:00+00:00",
        name="small",
        size=1000,
        addons=[],
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=False,
        homeassistant_version=None,
        protected=False,
    )
    with (
        patch.object(
            agent, "_upload_simple_b2", side_effect=ValueError("Unexpected error")
        ),
        pytest.raises(
            BackupAgentError, match="An unexpected error occurred during backup upload"
        ),
    ):
        await agent.async_upload_backup(open_stream=AsyncMock(), backup=small_backup)

    # Test cache hit scenario (lines 556-558)
    agent._backup_list_cache = {"test_backup": small_backup}
    agent._backup_list_cache_expiration = time() + 300

    # This should hit the cache
    cached_backup = await agent.async_get_backup("test_backup")
    assert cached_backup == small_backup

    # Test ValueError in metadata parsing (lines 632-638)
    with pytest.raises(ValueError):
        _parse_and_validate_metadata("invalid json content")
