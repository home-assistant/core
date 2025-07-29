"""Test Backblaze backup agent."""

from collections.abc import AsyncGenerator
import io
import json
import logging
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from b2sdk.v2 import DEFAULT_MIN_PART_SIZE
from b2sdk.v2.exception import B2Error
import pytest

from homeassistant.components.backblaze.backup import (
    METADATA_VERSION,
    BackblazeBackupAgent,
    async_get_backup_agents,
    async_register_backup_agents_listener,
    handle_b2_errors,
    suggested_filename,
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
from .conftest import FileVersion
from .const import BACKUP_METADATA, METADATA_FILE_SUFFIX, TEST_BACKUP

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator

# ============================================================================
# FIXTURES
# ============================================================================


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


@pytest.fixture
async def backblaze_agent(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> BackblazeBackupAgent:
    """Return a BackblazeBackupAgent instance."""
    agents = await async_get_backup_agents(hass)
    for entry in agents:
        if (
            isinstance(entry, BackblazeBackupAgent)
            and entry.unique_id == mock_config_entry.entry_id
        ):
            return entry
    pytest.fail("BackblazeBackupAgent not found")


@pytest.fixture
def mock_file_versions(mock_config_entry: MockConfigEntry, test_backup: AgentBackup):
    """Create mock file versions for testing."""
    # Main backup file
    mock_backup_file = Mock(spec=FileVersion)
    mock_backup_file.file_name = (
        f"{mock_config_entry.data['prefix']}{test_backup.backup_id}.tar"
    )
    mock_backup_file.upload_timestamp = 1672531200000
    mock_backup_file.file_id = "backup_file_id"
    mock_backup_file.size = test_backup.size
    mock_backup_file.delete = MagicMock()

    # Metadata file
    mock_metadata_file = Mock(spec=FileVersion)
    mock_metadata_file.file_name = f"{mock_config_entry.data['prefix']}{test_backup.backup_id}.tar{METADATA_FILE_SUFFIX}"
    mock_metadata_file.upload_timestamp = 1672531200000
    mock_metadata_file.file_id = "metadata_file_id"
    mock_metadata_file.delete = MagicMock()

    # Mock metadata content
    valid_metadata_content = json.dumps(BACKUP_METADATA)
    mock_metadata_file.download.return_value.response.content = (
        valid_metadata_content.encode("utf-8")
    )

    return mock_backup_file, mock_metadata_file


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def create_mock_stream_callable(chunks: list[bytes]) -> AsyncMock:
    """Create a mock stream callable that yields the given chunks."""
    mock_callable = AsyncMock()

    async def chunk_generator():
        for chunk in chunks:
            yield chunk
        yield b""  # End of stream marker

    mock_callable.return_value = chunk_generator()
    return mock_callable


def create_metadata_file(
    prefix: str,
    backup_id: str,
    metadata: dict | None = None,
    error: Exception | None = None,
    corrupted: bool = False,
) -> Mock:
    """Create a mock metadata file with various states."""
    mock_file = Mock(spec=FileVersion)
    mock_file.file_name = f"{prefix}{backup_id}.tar{METADATA_FILE_SUFFIX}"
    mock_file.upload_timestamp = 1672531200000
    mock_file.file_id = f"{backup_id}_metadata_id"
    mock_file.delete = MagicMock()

    if error:
        mock_file.download.side_effect = error
    elif corrupted:
        mock_file.download.return_value.response.content = b"{invalid json content"
    else:
        content = metadata or BACKUP_METADATA
        mock_file.download.return_value.response.content = json.dumps(content).encode(
            "utf-8"
        )

    return mock_file


# ============================================================================
# BASIC FUNCTIONALITY TESTS
# ============================================================================


async def test_suggested_filenames() -> None:
    """Test the suggested_filenames function."""
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
    metadata_filename = tar_filename + METADATA_FILE_SUFFIX

    assert tar_filename == "my_pretty_backup_2021-01-01_01.02_03000000.tar"
    assert (
        metadata_filename
        == "my_pretty_backup_2021-01-01_01.02_03000000.tar.metadata.json"
    )


# ============================================================================
# WEBSOCKET API TESTS
# ============================================================================


class TestWebSocketAPI:
    """Test WebSocket API functionality."""

    async def test_agents_info(
        self,
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
        self,
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
        assert len(response["result"]["backups"]) == 1

        backup = response["result"]["backups"][0]
        assert backup["backup_id"] == TEST_BACKUP.backup_id
        assert f"{DOMAIN}.{mock_config_entry.entry_id}" in backup["agents"]

    async def test_agents_get_backup(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        mock_config_entry: MockConfigEntry,
        test_backup: AgentBackup,
    ) -> None:
        """Test agent get backup."""
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": test_backup.backup_id}
        )
        response = await client.receive_json()

        assert response["success"]
        assert response["result"]["agent_errors"] == {}
        backup = response["result"]["backup"]
        assert backup["backup_id"] == test_backup.backup_id
        assert f"{DOMAIN}.{mock_config_entry.entry_id}" in backup["agents"]

    @pytest.mark.parametrize(
        ("list_objects_return_value", "find_file_return_value"),
        [
            ({"Contents": []}, (None, None)),
            ({"Contents": [{"fileName": "some.tar"}]}, (None, None)),
        ],
        ids=["empty_bucket", "no_matching_files"],
    )
    async def test_agents_get_backup_not_found(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        list_objects_return_value: dict,
        find_file_return_value: tuple,
    ) -> None:
        """Test agent get backup when backup not found."""
        with (
            patch(
                "b2sdk._internal.raw_simulator.BucketSimulator.ls",
                return_value=list_objects_return_value["Contents"],
            ),
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
                return_value=find_file_return_value,
            ),
        ):
            client = await hass_ws_client(hass)
            await client.send_json_auto_id(
                {"type": "backup/details", "backup_id": "random"}
            )
            response = await client.receive_json()

        assert response["success"]
        assert response["result"]["backup"] is None


# ============================================================================
# METADATA PROCESSING TESTS
# ============================================================================


class TestMetadataProcessing:
    """Test metadata file processing scenarios."""

    @pytest.mark.parametrize(
        ("metadata_type", "expected_log_level", "expected_logs"),
        [
            ("corrupted", logging.WARNING, ["Failed to parse metadata file"]),
            (
                "b2_error",
                logging.WARNING,
                ["Failed to parse metadata file", "B2 error"],
            ),
            (
                "missing_backup_id",
                logging.DEBUG,
                ["Skipping non-conforming metadata file"],
            ),
            (
                "wrong_version",
                logging.DEBUG,
                ["Skipping non-conforming metadata file"],
            ),
        ],
        ids=[
            "corrupted_json",
            "b2_download_error",
            "missing_backup_id",
            "wrong_version",
        ],
    )
    async def test_metadata_processing_scenarios(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
        test_backup: AgentBackup,
        metadata_type: str,
        expected_log_level: int,
        expected_logs: list[str],
    ) -> None:
        """Test various metadata processing error scenarios."""
        agent = BackblazeBackupAgent(hass, mock_config_entry)
        prefix = mock_config_entry.data["prefix"]

        # Create valid backup files
        mock_tar_file = Mock(spec=FileVersion)
        mock_tar_file.file_name = f"{prefix}{test_backup.backup_id}.tar"
        mock_tar_file.size = test_backup.size

        mock_valid_metadata = create_metadata_file(prefix, test_backup.backup_id)

        # Create problematic metadata based on type
        if metadata_type == "corrupted":
            mock_problem = create_metadata_file(prefix, "problem", corrupted=True)
        elif metadata_type == "b2_error":
            mock_problem = create_metadata_file(
                prefix, "problem", error=B2Error("B2 error")
            )
        elif metadata_type == "missing_backup_id":
            mock_problem = create_metadata_file(
                prefix, "problem", {"metadata_version": METADATA_VERSION}
            )
        else:  # wrong_version
            mock_problem = create_metadata_file(
                prefix, "problem", {"metadata_version": "2", "backup_id": "test"}
            )

        mock_all_files = {
            mock_valid_metadata.file_name: mock_valid_metadata,
            mock_problem.file_name: mock_problem,
            mock_tar_file.file_name: mock_tar_file,
        }

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
                return_value=mock_all_files,
            ),
            caplog.at_level(expected_log_level),
        ):
            backups = await agent.async_list_backups()

            # Only the valid backup should be returned
            assert len(backups) == 1
            assert backups[0].backup_id == test_backup.backup_id

            # Check expected log messages
            for expected_log in expected_logs:
                assert expected_log in caplog.text

    async def test_metadata_without_backup_file(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test metadata file exists but backup file is missing."""
        agent = BackblazeBackupAgent(hass, mock_config_entry)
        prefix = mock_config_entry.data["prefix"]

        mock_metadata_only = create_metadata_file(
            prefix,
            "orphaned_backup",
            {
                "metadata_version": METADATA_VERSION,
                "backup_id": "orphaned_backup",
                "backup_metadata": TEST_BACKUP.as_dict(),
            },
        )

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
                return_value={mock_metadata_only.file_name: mock_metadata_only},
            ),
            caplog.at_level(logging.WARNING),
        ):
            backups = await agent.async_list_backups()
            assert len(backups) == 0
            assert "Found metadata file" in caplog.text
            assert "but no corresponding backup file" in caplog.text


# ============================================================================
# UPLOAD TESTS
# ============================================================================


class TestUploadFunctionality:
    """Test backup upload functionality."""

    @pytest.mark.parametrize(
        ("backup_size", "upload_method", "expected_log"),
        [
            (100, "simple", "Simple upload finished"),
            (DEFAULT_MIN_PART_SIZE * 2, "multipart", "Successfully uploaded"),
        ],
        ids=["simple_upload", "multipart_upload"],
    )
    async def test_upload_methods(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
        backup_size: int,
        upload_method: str,
        expected_log: str,
    ) -> None:
        """Test both simple and multipart upload methods."""
        client = await hass_client()
        backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": backup_size})

        chunk_size = min(backup_size, DEFAULT_MIN_PART_SIZE)
        chunks = [b"test" * (chunk_size // 4)]
        if backup_size > DEFAULT_MIN_PART_SIZE:
            chunks.append(b"test" * ((backup_size - chunk_size) // 4))

        mock_open_stream_callable = create_mock_stream_callable(chunks)
        mock_bucket = Mock()
        mock_bucket.upload_bytes.return_value = Mock(id_="test_simple_id")
        mock_bucket.upload_local_file.return_value = Mock(id_="test_multipart_id")

        patch_target = (
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_multipart_b2"
            if upload_method == "simple"
            else "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_simple_b2"
        )

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
            patch(patch_target, autospec=True) as mock_unused_method,
            caplog.at_level(logging.INFO),
        ):
            agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)
            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable, backup=backup
            )

        assert not mock_unused_method.called
        assert expected_log in caplog.text

    @pytest.mark.parametrize(
        ("failure_point", "exception_type", "expected_logs"),
        [
            (
                "multipart",
                Exception("Multipart error"),
                ["Upload failed", "Multipart error"],
            ),
            ("metadata", BackupAgentError("Metadata error"), ["Metadata error"]),
            (
                "simple",
                ValueError("Simple error"),
                ["unexpected error", "Simple error"],
            ),
        ],
        ids=["multipart_failure", "metadata_failure", "simple_failure"],
    )
    async def test_upload_failures(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
        failure_point: str,
        exception_type: Exception,
        expected_logs: list[str],
    ) -> None:
        """Test various upload failure scenarios."""
        client = await hass_client()
        backup_size = DEFAULT_MIN_PART_SIZE * 2 if failure_point == "multipart" else 100
        backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": backup_size})

        patch_targets = {
            "multipart": "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_multipart_b2",
            "metadata": "homeassistant.components.backblaze.backup.BackblazeBackupAgent.async_upload_backup",
            "simple": "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_simple_b2",
        }

        with (
            patch(
                "homeassistant.components.backup.manager.BackupManager.async_get_backup",
                return_value=backup,
            ),
            patch(
                "homeassistant.components.backup.manager.read_backup",
                return_value=backup,
            ),
            patch(
                "pathlib.Path.open",
                return_value=Mock(read=Mock(side_effect=[b"test", b""])),
            ),
            patch(patch_targets[failure_point], side_effect=exception_type),
            caplog.at_level(logging.ERROR),
        ):
            resp = await client.post(
                f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
                data={"file": io.StringIO("test")},
            )

        assert resp.status == 201
        for expected_log in expected_logs:
            assert expected_log in caplog.text


# ============================================================================
# DOWNLOAD TESTS
# ============================================================================


class TestDownloadFunctionality:
    """Test backup download functionality."""

    async def test_successful_download(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        test_backup: AgentBackup,
    ) -> None:
        """Test successful backup download."""
        with patch("b2sdk.v2.FileVersion.download") as mock_download:
            mock_download.return_value.response.iter_content.return_value = iter(
                [b"backup data"]
            )
            mock_download.return_value.response.content = json.dumps(
                BACKUP_METADATA
            ).encode("utf-8")

            client = await hass_client()
            resp = await client.get(
                f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
            )

            assert resp.status == 200
            assert await resp.content.read() == b"backup data"

    async def test_download_not_found(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test download when backup is not found."""
        with patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
            return_value=(None, None),
        ):
            client = await hass_client()
            resp = await client.get(
                f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
            )

            assert resp.status == 404


# ============================================================================
# DELETE TESTS
# ============================================================================


class TestDeleteFunctionality:
    """Test backup deletion functionality."""

    async def test_successful_delete(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        mock_config_entry: MockConfigEntry,
        test_backup: AgentBackup,
        mock_file_versions,
    ) -> None:
        """Test successful backup deletion."""
        mock_backup_file, mock_metadata_file = mock_file_versions

        with patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
            return_value=(mock_backup_file, mock_metadata_file),
        ):
            client = await hass_ws_client(hass)
            await client.send_json_auto_id(
                {
                    "type": "backup/delete",
                    "backup_id": test_backup.backup_id,
                }
            )
            response = await client.receive_json()

        assert response["success"]
        assert response["result"] == {"agent_errors": {}}
        mock_backup_file.delete.assert_called_once()
        mock_metadata_file.delete.assert_called_once()

    @pytest.mark.parametrize(
        (
            "backup_file",
            "metadata_file",
            "metadata_error",
            "expected_error",
            "expected_logs",
        ),
        [
            (Mock(spec=FileVersion), None, None, False, ["not found for deletion"]),
            (
                Mock(spec=FileVersion),
                Mock(spec=FileVersion),
                B2Error("B2 delete error"),
                True,
                ["Failed to delete metadata"],
            ),
            (None, None, None, False, []),  # Backup not found
        ],
        ids=["metadata_missing", "b2_delete_error", "backup_not_found"],
    )
    async def test_delete_scenarios(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
        backup_file: Mock | None,
        metadata_file: Mock | None,
        metadata_error: Exception | None,
        expected_error: bool,
        expected_logs: list[str],
    ) -> None:
        """Test various deletion scenarios."""
        if backup_file:
            backup_file.delete = Mock()
        if metadata_file:
            metadata_file.delete = Mock(side_effect=metadata_error)

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
                return_value=(backup_file, metadata_file),
            ),
            caplog.at_level(logging.DEBUG),
        ):
            client = await hass_ws_client(hass)

            if backup_file is None and metadata_file is None:
                # Test the agent method directly for BackupNotFound exception
                agent = BackblazeBackupAgent(hass, mock_config_entry)
                with pytest.raises(BackupNotFound):
                    await agent.async_delete_backup(TEST_BACKUP.backup_id)

            await client.send_json_auto_id(
                {
                    "type": "backup/delete",
                    "backup_id": TEST_BACKUP.backup_id,
                }
            )
            response = await client.receive_json()

        assert response["success"]

        if expected_error:
            assert (
                "Failed during async_delete_backup"
                in response["result"]["agent_errors"][
                    f"{DOMAIN}.{mock_config_entry.entry_id}"
                ]
            )
        else:
            assert response["result"] == {"agent_errors": {}}

        for expected_log in expected_logs:
            assert expected_log in caplog.text


# ============================================================================
# UTILITY AND ERROR HANDLING TESTS
# ============================================================================


class TestUtilityFunctions:
    """Test utility functions and error handling."""

    async def test_listeners_cleanup(self, hass: HomeAssistant) -> None:
        """Test listener cleanup."""
        listener = MagicMock()
        remove_listener = async_register_backup_agents_listener(hass, listener=listener)

        hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]
        remove_listener()

        assert DATA_BACKUP_AGENT_LISTENERS not in hass.data

    async def test_handle_b2_errors_decorator(self) -> None:
        """Test handle_b2_errors decorator."""

        @handle_b2_errors
        async def mock_func_raises_b2_error() -> None:
            raise B2Error("test error")

        with pytest.raises(
            BackupAgentError, match="Failed during mock_func_raises_b2_error"
        ):
            await mock_func_raises_b2_error()

    async def test_stream_cleanup(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that streams are properly closed during upload."""
        client = await hass_client()
        backup = AgentBackup(
            **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2}
        )

        class MockStream:
            def __init__(self, close_method: str) -> None:
                self.close_method = close_method
                self.closed = False

            async def __aiter__(self):
                yield b"chunk1"
                yield b"chunk2"

            def close(self):
                if self.close_method == "close":
                    self.closed = True

            async def aclose(self):
                if self.close_method == "aclose":
                    self.closed = True

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.close_method == "close":
                    self.close()
                else:
                    await self.aclose()

        for close_method in ("close", "aclose"):
            stream = MockStream(close_method)
            mock_open_stream_callable = AsyncMock(return_value=stream)

            with (
                patch(
                    "homeassistant.components.backup.manager.BackupManager.async_get_backup",
                    return_value=backup,
                ),
                patch(
                    "homeassistant.components.backup.manager.read_backup",
                    return_value=backup,
                ),
                patch.object(mock_config_entry, "runtime_data", new=Mock()),
                patch("homeassistant.components.backblaze.backup.aiofiles.open"),
            ):
                agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)
                await agent.async_upload_backup(
                    open_stream=mock_open_stream_callable, backup=backup
                )
                assert stream.closed

    @pytest.mark.parametrize(
        ("error_type", "expected_log"),
        [
            (B2Error("B2 connection error"), "B2 connection error during upload"),
            (Exception("Unexpected error"), "An error occurred during upload"),
        ],
        ids=["b2_error", "unexpected_error"],
    )
    async def test_multipart_upload_errors(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
        error_type: Exception,
        expected_log: str,
    ) -> None:
        """Test multipart upload error handling."""
        client = await hass_client()
        backup = AgentBackup(
            **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2}
        )
        mock_open_stream_callable = create_mock_stream_callable([b"chunk1", b"chunk2"])

        with (
            patch.object(mock_config_entry, "runtime_data", new=Mock()),
            patch(
                "homeassistant.components.backblaze.backup.aiofiles.open",
                side_effect=error_type,
            ),
            caplog.at_level(logging.ERROR),
        ):
            agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

            with pytest.raises(BackupAgentError):
                await agent.async_upload_backup(
                    open_stream=mock_open_stream_callable, backup=backup
                )

            assert expected_log in caplog.text
