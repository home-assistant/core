"""Test Backblaze backup agent."""

from collections.abc import AsyncGenerator
import io
import json
import logging
from time import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from b2sdk.v2 import DEFAULT_MIN_PART_SIZE
from b2sdk.v2.exception import B2Error
import pytest

from homeassistant.components.backblaze.backup import (
    CACHE_TTL,
    BackblazeBackupAgent,
    async_get_backup_agents,
    async_register_backup_agents_listener,
    handle_b2_errors,
    suggested_filename,
)
from homeassistant.components.backblaze.const import (
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    METADATA_VERSION,
)
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


def create_corrupted_metadata_file(prefix: str, backup_id: str) -> Mock:
    """Create a mock file version with corrupted metadata."""
    mock_file = Mock(spec=FileVersion)
    mock_file.file_name = f"{prefix}{backup_id}.tar{METADATA_FILE_SUFFIX}"
    mock_file.upload_timestamp = 1672531200000
    mock_file.file_id = f"corrupted_{backup_id}_id"
    mock_file.download.return_value.response.content = b"{invalid json content"
    return mock_file


def create_b2_error_metadata_file(prefix: str, backup_id: str, error_msg: str) -> Mock:
    """Create a mock file version that raises B2Error on download."""
    mock_file = Mock(spec=FileVersion)
    mock_file.file_name = f"{prefix}{backup_id}.tar{METADATA_FILE_SUFFIX}"
    mock_file.upload_timestamp = 1672531200000
    mock_file.file_id = f"b2error_{backup_id}_id"
    mock_file.download.side_effect = B2Error(error_msg)
    return mock_file


def create_non_conforming_metadata_file(
    prefix: str, backup_id: str, metadata: dict
) -> Mock:
    """Create a mock file version with non-conforming metadata."""
    mock_file = Mock(spec=FileVersion)
    mock_file.file_name = f"{prefix}{backup_id}.tar{METADATA_FILE_SUFFIX}"
    mock_file.upload_timestamp = 1672531200000
    mock_file.file_id = f"nonconform_{backup_id}_id"
    mock_file.download.return_value.response.content = json.dumps(metadata).encode(
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
        assert response["result"]["backup"] == {
            "addons": [],
            "backup_id": test_backup.backup_id,
            "date": test_backup.date,
            "database_included": test_backup.database_included,
            "folders": test_backup.folders,
            "homeassistant_included": test_backup.homeassistant_included,
            "homeassistant_version": test_backup.homeassistant_version,
            "name": test_backup.name,
            "extra_metadata": test_backup.extra_metadata,
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

    @pytest.mark.parametrize(
        (
            "list_objects_return_value",
            "find_file_return_value",
            "expected_backup_is_none",
        ),
        [
            ({"Contents": []}, (None, None), True),
            ({"Contents": [{"fileName": "some.tar"}]}, (None, None), True),
        ],
        ids=["b2_ls_empty", "find_file_and_metadata_returns_none"],
    )
    async def test_agents_get_backup_not_found_scenarios(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        list_objects_return_value: dict,
        find_file_return_value: tuple,
        expected_backup_is_none: bool,
    ) -> None:
        """Test agent get backup does not throw on a backup not found."""
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
        assert response["result"]["agent_errors"] == {}
        assert (response["result"]["backup"] is None) == expected_backup_is_none


# ============================================================================
# METADATA PROCESSING TESTS
# ============================================================================


class TestMetadataProcessing:
    """Test metadata file processing scenarios."""

    async def test_list_backups_with_corrupted_metadata(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
        test_backup: AgentBackup,
    ) -> None:
        """Test listing backups when one metadata file is corrupted or non-conforming."""
        agent = BackblazeBackupAgent(hass, mock_config_entry)
        prefix = mock_config_entry.data["prefix"]

        # Create valid backup files
        valid_backup_core_name = f"{test_backup.backup_id}.tar"
        mock_tar_file = Mock(spec=FileVersion)
        mock_tar_file.file_name = f"{prefix}{valid_backup_core_name}"
        mock_tar_file.upload_timestamp = 1672531200000
        mock_tar_file.file_id = "tar_id"
        mock_tar_file.size = test_backup.size

        mock_valid_metadata = Mock(spec=FileVersion)
        mock_valid_metadata.file_name = (
            f"{prefix}{valid_backup_core_name}{METADATA_FILE_SUFFIX}"
        )
        mock_valid_metadata.upload_timestamp = 1672531200000
        mock_valid_metadata.file_id = "valid_id"
        valid_metadata_content = json.dumps(BACKUP_METADATA)
        mock_valid_metadata.download.return_value.response.content = (
            valid_metadata_content.encode("utf-8")
        )

        # Create problematic files
        mock_corrupted = create_corrupted_metadata_file(prefix, "corrupted_backup_id")
        mock_b2_error = create_b2_error_metadata_file(
            prefix, "b2_error_file", "simulated B2 error"
        )
        mock_missing_id = create_non_conforming_metadata_file(
            prefix, "non_conforming_missing_id", {"metadata_version": METADATA_VERSION}
        )
        mock_wrong_version = create_non_conforming_metadata_file(
            prefix,
            "non_conforming_wrong_version",
            {"metadata_version": "2", "backup_id": "test"},
        )

        mock_all_files = {
            mock_valid_metadata.file_name: mock_valid_metadata,
            mock_corrupted.file_name: mock_corrupted,
            mock_missing_id.file_name: mock_missing_id,
            mock_wrong_version.file_name: mock_wrong_version,
            mock_b2_error.file_name: mock_b2_error,
            mock_tar_file.file_name: mock_tar_file,
        }

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
                return_value=mock_all_files,
            ),
            caplog.at_level(logging.DEBUG),
        ):
            # Adds coverage
            agent._backup_list_cache_expiration = time() + CACHE_TTL
            await agent.async_get_backup(test_backup.backup_id)

            # List backups, which should process the metadata files
            agent._backup_list_cache_expiration = 0.0
            backups = await agent.async_list_backups()

            # Adds coverage
            await agent.async_get_backup(test_backup.backup_id)

            # Only the valid backup should be returned
            assert len(backups) == 1
            assert backups[0].backup_id == test_backup.backup_id

            # Assert that specific log messages are present
            assert "Failed to parse metadata file" in caplog.text
            assert "Skipping non-conforming metadata file" in caplog.text
            assert "simulated B2 error" in caplog.text

    async def test_metadata_processing_detailed_scenarios(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test detailed metadata processing scenarios with specific log messages."""
        agent = BackblazeBackupAgent(hass, mock_config_entry)
        prefix = mock_config_entry.data["prefix"]

        test_scenarios = [
            # Scenario 1: Metadata exists but backup file missing
            {
                "name": "metadata_exists_backup_missing",
                "log_level": logging.WARNING,
                "expected_log": "Found metadata file",
                "files": {
                    f"{prefix}test_backup.tar{METADATA_FILE_SUFFIX}": Mock(
                        spec=FileVersion,
                        file_name=f"{prefix}test_backup.tar{METADATA_FILE_SUFFIX}",
                        download=Mock(
                            return_value=Mock(
                                response=Mock(
                                    content=json.dumps(
                                        {
                                            "metadata_version": METADATA_VERSION,
                                            "backup_id": "test_backup",
                                            "backup_metadata": TEST_BACKUP.as_dict(),
                                        }
                                    ).encode("utf-8")
                                )
                            )
                        ),
                    )
                },
            },
            # Scenario 2: Corrupted JSON
            {
                "name": "corrupted_json",
                "log_level": logging.WARNING,
                "expected_log": "",
                "files": {
                    f"{prefix}corrupted_backup.tar{METADATA_FILE_SUFFIX}": create_corrupted_metadata_file(
                        prefix, "corrupted_backup"
                    )
                },
            },
            # Scenario 3: B2Error during download
            {
                "name": "b2_error_download",
                "log_level": logging.WARNING,
                "expected_log": "",
                "files": {
                    f"{prefix}b2error_backup.tar{METADATA_FILE_SUFFIX}": create_b2_error_metadata_file(
                        prefix,
                        "b2error_backup",
                        "Simulated B2 download error for metadata",
                    )
                },
            },
        ]

        for scenario in test_scenarios:
            caplog.clear()
            with (
                caplog.at_level(scenario["log_level"]),
                patch(
                    "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
                    return_value=scenario["files"],
                ),
            ):
                result = await agent.async_list_backups()
                assert len(result) == 0
                assert scenario["expected_log"] in caplog.text

    async def test_metadata_id_mismatch_scenarios(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test scenarios for metadata ID mismatches and missing files."""
        agent = BackblazeBackupAgent(hass, mock_config_entry)
        prefix = mock_config_entry.data["prefix"]

        # Scenario: Metadata ID doesn't match target
        mock_metadata_mismatch = Mock(spec=FileVersion)
        mock_metadata_mismatch.file_name = (
            f"{prefix}another_backup.tar{METADATA_FILE_SUFFIX}"
        )
        mock_metadata_mismatch.download.return_value.response.content = json.dumps(
            {
                "metadata_version": METADATA_VERSION,
                "backup_id": "different_id",
                "backup_metadata": TEST_BACKUP.as_dict(),
            }
        ).encode("utf-8")

        mock_tar_file = Mock(spec=FileVersion)
        mock_tar_file.file_name = f"{prefix}another_backup.tar"

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
                return_value={
                    mock_metadata_mismatch.file_name: mock_metadata_mismatch,
                    mock_tar_file.file_name: mock_tar_file,
                },
            ),
            caplog.at_level(logging.DEBUG),
        ):
            target_id = "some_non_matching_id"
            (
                backup_file,
                metadata_file,
            ) = await agent._find_file_and_metadata_version_by_id(target_id)

            assert backup_file is None
            assert metadata_file is None
            assert f"does not match target backup ID {target_id}" in caplog.text


# ============================================================================
# UPLOAD TESTS
# ============================================================================


class TestUploadFunctionality:
    """Test backup upload functionality."""

    async def test_simple_file_upload(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test simple file upload for small backups."""
        client = await hass_client()
        backup_with_size = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100})

        mock_open_stream_callable = create_mock_stream_callable([b"test" * 25])

        mock_bucket = Mock()
        mock_file_version_result = Mock(spec=FileVersion)
        mock_file_version_result.id_ = "test_simple_file_id_456"
        mock_bucket.upload_file.return_value = mock_file_version_result

        with (
            patch(
                "homeassistant.components.backup.manager.BackupManager.async_get_backup",
                return_value=backup_with_size,
            ),
            patch(
                "homeassistant.components.backup.manager.read_backup",
                return_value=backup_with_size,
            ),
            patch.object(mock_config_entry, "runtime_data", new=mock_bucket),
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_multipart_b2",
                autospec=True,
            ) as mock_upload_multipart_b2,
            caplog.at_level(logging.INFO),
        ):
            agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)
            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable, backup=backup_with_size
            )

        assert not mock_upload_multipart_b2.called
        assert mock_bucket.upload_bytes.call_count == 2
        assert "Simple upload finished for" in caplog.text

    async def test_multipart_file_upload(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test multipart upload for large backups."""
        client = await hass_client()
        backup_with_size = AgentBackup(
            **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 1.05}
        )

        expected_b2_file_name = mock_config_entry.data["prefix"] + suggested_filename(
            backup_with_size
        )

        mock_open_stream_callable = create_mock_stream_callable(
            [
                b"test" * DEFAULT_MIN_PART_SIZE,
                b"test" * int(DEFAULT_MIN_PART_SIZE * 0.05),
            ]
        )

        mock_bucket = Mock()
        mock_file_version_result = Mock()
        mock_file_version_result.id_ = "test_file_id_123"
        mock_bucket.upload_local_file.return_value = mock_file_version_result

        with (
            patch(
                "homeassistant.components.backup.manager.BackupManager.async_get_backup",
                return_value=backup_with_size,
            ),
            patch(
                "homeassistant.components.backup.manager.read_backup",
                return_value=backup_with_size,
            ),
            patch.object(mock_config_entry, "runtime_data", new=mock_bucket),
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_simple_b2",
                autospec=True,
            ) as mock_upload_simple_b2,
            caplog.at_level(logging.INFO),
        ):
            agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)
            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable, backup=backup_with_size
            )

        assert not mock_upload_simple_b2.called
        mock_bucket.upload_local_file.assert_called_once()

        call_args, call_kwargs = mock_bucket.upload_local_file.call_args
        assert call_kwargs["file_name"] == expected_b2_file_name
        assert f"Successfully uploaded {expected_b2_file_name}" in caplog.text

    async def test_upload_failure_scenarios(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test various upload failure scenarios."""
        client = await hass_client()

        failure_scenarios = [
            {
                "name": "multipart_upload_fails",
                "backup_size": 100000000,
                "patch_target": "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_multipart_b2",
                "side_effect": Exception("Simulated multipart upload error"),
                "expected_logs": [
                    "Upload failed for backblaze",
                    "Simulated multipart upload error",
                ],
            },
            {
                "name": "metadata_upload_fails",
                "backup_size": 100,
                "patch_target": "homeassistant.components.backblaze.backup.BackblazeBackupAgent.async_upload_backup",
                "side_effect": BackupAgentError("Failed during upload_files"),
                "expected_logs": ["Failed during upload_files"],
            },
            {
                "name": "unexpected_error_during_upload",
                "backup_size": 100,
                "patch_target": "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_simple_b2",
                "side_effect": ValueError("Simulated unexpected error"),
                "expected_logs": [
                    "An unexpected error occurred during backup upload",
                    "Simulated unexpected error",
                ],
            },
        ]

        for scenario in failure_scenarios:
            caplog.clear()
            backup = AgentBackup(
                **{**TEST_BACKUP.as_dict(), "size": scenario["backup_size"]}
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
                patch("pathlib.Path.open") as mocked_open,
                patch(scenario["patch_target"], side_effect=scenario["side_effect"]),
                caplog.at_level(logging.ERROR),
            ):
                mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
                resp = await client.post(
                    f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
                    data={"file": io.StringIO("test")},
                )

            assert resp.status == 201
            for expected_log in scenario["expected_logs"]:
                assert expected_log in caplog.text

    async def test_metadata_upload_failure_cleanup(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test cleanup when metadata upload fails after successful backup upload."""
        client = await hass_client()
        backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100})

        mock_bucket = Mock()
        mock_file_version = Mock()
        mock_bucket.upload_bytes.side_effect = [
            mock_file_version,  # Success for backup file
            B2Error("Metadata upload failed (simulated)"),  # Failure for metadata
        ]
        mock_bucket.get_file_info_by_name.side_effect = Exception(
            "Cleanup file info lookup failed"
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
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_multipart_b2"
            ),
            caplog.at_level(logging.WARNING),
        ):
            mock_open_stream_callable = create_mock_stream_callable([b"test"])
            agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

            with pytest.raises(BackupAgentError) as excinfo:
                await agent.async_upload_backup(
                    open_stream=mock_open_stream_callable, backup=backup
                )

            assert "Failed to upload backup to Backblaze B2" in str(excinfo.value)
            assert "Metadata upload failed (simulated)" in str(excinfo.value)

            mock_bucket.get_file_info_by_name.assert_called_once()
            mock_file_version.delete.assert_not_called()

            expected_logs = [
                "Backblaze B2 API error during backup upload: Metadata upload failed (simulated)",
                "Attempting to delete partially uploaded main backup file",
                "Failed to clean up partially uploaded main backup file",
                "Cleanup file info lookup failed",
                "Manual intervention may be required to delete",
            ]
            for log in expected_logs:
                assert log in caplog.text


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
            backup_id = TEST_BACKUP.backup_id

            resp = await client.get(
                f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
            )
            assert resp.status == 200
            assert await resp.content.read() == b"backup data"

    @pytest.mark.parametrize(
        ("patch_target", "return_value", "expected_status"),
        [
            (
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
                (None, None),
                404,
            ),
        ],
        ids=["backup_not_found"],
    )
    async def test_download_backup_not_found(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        patch_target: str,
        return_value: tuple,
        expected_status: int,
    ) -> None:
        """Test download when backup is not found."""
        with patch(patch_target, return_value=return_value):
            client = await hass_client()
            backup_id = TEST_BACKUP.backup_id

            resp = await client.get(
                f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
            )
        assert resp.status == expected_status

    async def test_download_backup_not_found_exception(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test BackupNotFound exception during backup download."""
        client = await hass_client()
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        with patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
            return_value=(None, None),
        ):

            async def dummy_stream():
                yield b""

            with pytest.raises(BackupNotFound, match="Backup test_backup not found"):
                await agent.async_download_backup("test_backup", stream=dummy_stream())


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
        assert mock_backup_file.delete.call_count == 1
        assert mock_metadata_file.delete.call_count == 1

    @pytest.mark.parametrize(
        ("find_file_return_value", "delete_side_effect", "expected_agent_error"),
        [
            # Metadata file not found during delete
            ((Mock(spec=FileVersion, file_name="test.tar"), None), None, False),
            # B2Error during metadata file deletion
            (
                (
                    Mock(spec=FileVersion, file_name="test.tar"),
                    Mock(spec=FileVersion, file_name="test.tar.metadata.json"),
                ),
                B2Error("test b2 error during metadata delete"),
                True,
            ),
            # Backup not found
            ((None, None), None, False),
        ],
        ids=["metadata_not_found", "b2_error_on_metadata_delete", "backup_not_found"],
    )
    async def test_delete_scenarios(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
        find_file_return_value: tuple,
        delete_side_effect: Exception | None,
        expected_agent_error: bool,
    ) -> None:
        """Test various deletion scenarios."""
        mock_main_file_delete = Mock()
        mock_metadata_file_delete = Mock(side_effect=delete_side_effect)

        mock_backup_file, mock_metadata_file = find_file_return_value

        if mock_backup_file:
            mock_backup_file.delete = mock_main_file_delete
        if mock_metadata_file:
            mock_metadata_file.delete = mock_metadata_file_delete

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
                return_value=(mock_backup_file, mock_metadata_file),
            ),
            caplog.at_level(logging.DEBUG),
        ):
            agent = BackblazeBackupAgent(hass, mock_config_entry)
            client = await hass_ws_client(hass)

            if find_file_return_value == (None, None):
                with pytest.raises(BackupNotFound):
                    await agent.async_delete_backup(TEST_BACKUP.backup_id)

                await client.send_json_auto_id(
                    {
                        "type": "backup/delete",
                        "backup_id": TEST_BACKUP.backup_id,
                    }
                )
                response = await client.receive_json()

                assert response["success"] is True
                assert response["result"] == {"agent_errors": {}}
                assert mock_main_file_delete.call_count == 0
                assert mock_metadata_file_delete.call_count == 0
                return

            await client.send_json_auto_id(
                {
                    "type": "backup/delete",
                    "backup_id": TEST_BACKUP.backup_id,
                }
            )
            response = await client.receive_json()

        assert response["success"] is True

        if expected_agent_error:
            expected_response_error_msg = "Failed during async_delete_backup"
            assert response["result"] == {
                "agent_errors": {
                    f"{agent.domain}.{agent.unique_id}": expected_response_error_msg
                }
            }
            assert any(
                "Failed to delete metadata file" in s and str(delete_side_effect) in s
                for s in caplog.messages
            )
            assert mock_main_file_delete.call_count == 1
            assert mock_metadata_file_delete.call_count == 1
        else:
            assert response["result"] == {"agent_errors": {}}
            assert any(
                "Metadata file for backup" in s and "not found for deletion" in s
                for s in caplog.messages
            )
            assert mock_main_file_delete.call_count == 1
            assert mock_metadata_file_delete.call_count == 0

    async def test_metadata_deletion_unexpected_error(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test unexpected exceptions during metadata deletion."""
        agent = BackblazeBackupAgent(hass, mock_config_entry)

        mock_backup_file = Mock(spec=FileVersion)
        mock_metadata_file = Mock(spec=FileVersion)
        mock_metadata_file.delete.side_effect = Exception("Unexpected error")

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
                return_value=(mock_backup_file, mock_metadata_file),
            ),
            caplog.at_level(logging.ERROR),
        ):
            with pytest.raises(
                BackupAgentError, match="Unexpected error in metadata deletion"
            ):
                await agent.async_delete_backup("test_backup")

            mock_backup_file.delete.assert_called_once()
            assert "Unexpected error from executor for metadata" in caplog.text


# ============================================================================
# STREAM AND ERROR HANDLING TESTS
# ============================================================================


class TestStreamAndErrorHandling:
    """Test stream handling and error scenarios."""

    async def test_stream_closing_behavior(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that streams are properly closed during multipart upload."""
        client = await hass_client()
        backup = AgentBackup(
            **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2}
        )

        class MockStreamClose:
            def __init__(self) -> None:
                self.close_called = False

            async def __aiter__(self):
                yield b"chunk1"
                yield b"chunk2"

            def close(self):
                self.close_called = True

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.close()

        class MockStreamAclose:
            def __init__(self) -> None:
                self.aclose_called = False

            async def __aiter__(self):
                yield b"chunk1"
                yield b"chunk2"

            async def aclose(self):
                self.aclose_called = True

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                await self.aclose()

        stream_with_close = MockStreamClose()
        stream_with_aclose = MockStreamAclose()

        mock_open_stream_callable = AsyncMock()
        mock_open_stream_callable.side_effect = [stream_with_close, stream_with_aclose]

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
            assert stream_with_close.close_called

            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable, backup=backup
            )
            assert stream_with_aclose.aclose_called

    async def test_multipart_upload_exceptions(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test exception handling in multipart upload."""
        client = await hass_client()
        backup = AgentBackup(
            **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2}
        )

        mock_open_stream_callable = create_mock_stream_callable([b"chunk1", b"chunk2"])

        test_cases = [
            {
                "name": "b2_error",
                "side_effect": B2Error("B2 connection error"),
                "expected_log": "B2 connection error during upload",
            },
            {
                "name": "unexpected_error",
                "side_effect": Exception("Unexpected error"),
                "expected_log": "An error occurred during upload",
            },
        ]

        for case in test_cases:
            caplog.clear()
            with (
                patch.object(mock_config_entry, "runtime_data", new=Mock()),
                patch(
                    "homeassistant.components.backblaze.backup.aiofiles.open",
                    side_effect=case["side_effect"],
                ),
                caplog.at_level(logging.ERROR),
            ):
                agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

                with pytest.raises(BackupAgentError):
                    await agent.async_upload_backup(
                        open_stream=mock_open_stream_callable, backup=backup
                    )

                assert case["expected_log"] in caplog.text

    async def test_temp_file_cleanup_failure(
        self,
        hass_client: ClientSessionGenerator,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test temporary file cleanup failure during multipart upload."""
        client = await hass_client()
        backup = AgentBackup(
            **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2}
        )

        mock_open_stream_callable = create_mock_stream_callable([b"chunk1", b"chunk2"])
        mock_bucket = Mock()

        with (
            patch.object(mock_config_entry, "runtime_data", new=mock_bucket),
            patch("homeassistant.components.backblaze.backup.aiofiles.open"),
            patch("os.unlink", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.WARNING),
        ):
            agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)
            mock_bucket.upload_local_file.return_value = Mock()

            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable, backup=backup
            )

            assert any(
                "Failed to delete temporary file" in record.message
                for record in caplog.records
            )


# ============================================================================
# UTILITY AND MISCELLANEOUS TESTS
# ============================================================================


class TestUtilityFunctions:
    """Test utility functions and edge cases."""

    async def test_debug_log_backup_not_found(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test debug log when backup is not found during search."""
        agent = BackblazeBackupAgent(hass, mock_config_entry)

        with (
            patch(
                "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
                return_value={},
            ),
            caplog.at_level(logging.DEBUG),
        ):
            with pytest.raises(BackupNotFound):
                await agent.async_get_backup("non_existent_backup")

            assert "Backup non_existent_backup not found" in caplog.text

    async def test_listeners_cleanup(self, hass: HomeAssistant) -> None:
        """Test listener gets cleaned up."""
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


# ============================================================================
# COMPREHENSIVE METADATA LOGGING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_metadata_processing_comprehensive_log_scenarios(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test comprehensive metadata processing scenarios for complete log coverage."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    prefix = mock_config_entry.data["prefix"]

    # Scenario 1: Metadata exists but backup file missing (WARNING)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        mock_metadata_missing_backup = Mock(spec=FileVersion)
        mock_metadata_missing_backup.file_name = (
            f"{prefix}test_backup.tar{METADATA_FILE_SUFFIX}"
        )

        def mock_download_valid():
            mock_response = Mock()
            mock_response.content = json.dumps(
                {
                    "metadata_version": METADATA_VERSION,
                    "backup_id": "test_backup",
                    "backup_metadata": TEST_BACKUP.as_dict(),
                }
            ).encode("utf-8")
            return mock_response

        mock_metadata_missing_backup.download.return_value.response = (
            mock_download_valid()
        )

        with patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
            return_value={
                mock_metadata_missing_backup.file_name: mock_metadata_missing_backup
            },
        ):
            result = await agent.async_list_backups()
            assert len(result) == 0
            assert "Found metadata file" in caplog.text
            assert "but no corresponding backup file starting with" in caplog.text

            # Added coverage for attempted cache retrieval
            agent._backup_list_cache["dummy_backup_id"] = TEST_BACKUP
            agent._backup_list_cache_expiration = time() + CACHE_TTL
            result = await agent.async_list_backups()
            assert len(result) == 1

    # Scenario 2: Metadata ID doesn't match target (DEBUG)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        mock_metadata_mismatch = Mock(spec=FileVersion)
        mock_metadata_mismatch.file_name = (
            f"{prefix}another_backup.tar{METADATA_FILE_SUFFIX}"
        )

        def mock_download_mismatch():
            mock_response = Mock()
            mock_response.content = json.dumps(
                {
                    "metadata_version": METADATA_VERSION,
                    "backup_id": "different_id",
                    "backup_metadata": TEST_BACKUP.as_dict(),
                }
            ).encode("utf-8")
            return mock_response

        mock_metadata_mismatch.download.return_value.response = mock_download_mismatch()

        mock_tar_file = Mock(spec=FileVersion)
        mock_tar_file.file_name = f"{prefix}another_backup.tar"

        with patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
            return_value={
                mock_metadata_mismatch.file_name: mock_metadata_mismatch,
                mock_tar_file.file_name: mock_tar_file,
            },
        ):
            target_id = "some_non_matching_id"
            (
                backup_file,
                metadata_file,
            ) = await agent._find_file_and_metadata_version_by_id(target_id)

            assert backup_file is None
            assert metadata_file is None
            assert (
                f"does not match target backup ID {target_id} or version" in caplog.text
            )

    # Scenario 3: Metadata found but no corresponding backup file (for_id_sync)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        target_backup_id = "specific_backup_id"
        mock_metadata_only = Mock(spec=FileVersion)
        mock_metadata_only.file_name = (
            f"{prefix}{target_backup_id}.tar{METADATA_FILE_SUFFIX}"
        )

        def mock_download_valid_for_id():
            mock_response = Mock()
            mock_response.content = json.dumps(
                {
                    "metadata_version": METADATA_VERSION,
                    "backup_id": target_backup_id,
                    "backup_metadata": TEST_BACKUP.as_dict(),
                }
            ).encode("utf-8")
            return mock_response

        mock_metadata_only.download.return_value.response = mock_download_valid_for_id()

        with patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
            return_value={mock_metadata_only.file_name: mock_metadata_only},
        ):
            (
                backup_file,
                metadata_file,
            ) = await agent._find_file_and_metadata_version_by_id(target_backup_id)

            assert backup_file is None
            assert metadata_file is None
            assert (
                f"Found metadata file {mock_metadata_only.file_name} for backup ID {target_backup_id}, but no corresponding backup file"
                in caplog.text
            )

    # Scenario 4: Metadata parsing fails during ID search (for_id_sync)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        target_backup_id_faulty = "faulty_backup_id"
        mock_metadata_faulty = Mock(spec=FileVersion)
        mock_metadata_faulty.file_name = (
            f"{prefix}{target_backup_id_faulty}.tar{METADATA_FILE_SUFFIX}"
        )

        def mock_download_faulty():
            mock_response = Mock()
            mock_response.content = b"not json at all"
            return mock_response

        mock_metadata_faulty.download.return_value.response = mock_download_faulty()

        mock_tar_file_faulty = Mock(spec=FileVersion)
        mock_tar_file_faulty.file_name = f"{prefix}{target_backup_id_faulty}.tar"

        with patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
            return_value={
                mock_metadata_faulty.file_name: mock_metadata_faulty,
                mock_tar_file_faulty.file_name: mock_tar_file_faulty,
            },
        ):
            (
                backup_file,
                metadata_file,
            ) = await agent._find_file_and_metadata_version_by_id(
                target_backup_id_faulty
            )

            assert backup_file is None
            assert metadata_file is None
            assert (
                f"Failed to parse metadata file {mock_metadata_faulty.file_name} during ID search: Expecting value: line 1 column 1 (char 0)"
                in caplog.text
            )
