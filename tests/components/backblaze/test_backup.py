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
    ("list_objects_return_value", "find_file_return_value", "expected_backup_is_none"),
    [
        ({"Contents": []}, (None, None), True),  # b2 ls empty
        (
            {"Contents": [{"fileName": "some.tar"}]},
            (None, None),
            True,
        ),  # find_file_and_metadata_version_by_id returns None,None
    ],
    ids=["b2_ls_empty", "find_file_and_metadata_returns_none"],
)
async def test_agents_get_backup_does_not_throw_on_not_found(
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


async def test_agents_list_backups_with_corrupted_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    test_backup: AgentBackup,
) -> None:
    """Test listing backups when one metadata file is corrupted or non-conforming.

    This test verifies that the BackblazeBackupAgent correctly handles various
    scenarios of invalid or unreadable metadata files when listing backups,
    ensuring only valid backups are returned and appropriate errors are logged.
    """
    # Create an instance of the BackblazeBackupAgent.
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    # --- Set up mock responses for different types of metadata files ---

    # Use test_backup.backup_id directly for simpler filename matching
    # The agent's _process_metadata_file_sync will derive the backup_id from the filename
    # by stripping the prefix and '.tar.metadata.json' suffix.
    # So, the core part of the filename should be the backup_id + '.tar'
    valid_backup_core_name = f"{test_backup.backup_id}.tar"

    # 0. Mock for the main backup archive file (.tar).
    # This file is needed for the valid metadata to find its corresponding archive.
    mock_file_version_tar = Mock(spec=FileVersion)
    mock_file_version_tar.file_name = (
        f"{mock_config_entry.data['prefix']}{valid_backup_core_name}"
    )
    mock_file_version_tar.upload_timestamp = 1672531200000
    mock_file_version_tar.file_id = "tar_id"
    mock_file_version_tar.size = (
        test_backup.size
    )  # Ensure size matches for AgentBackup creation

    # 1. Mock for a valid metadata file.
    # This file will be successfully parsed and represent a valid backup.
    mock_file_version_valid = Mock(spec=FileVersion)
    mock_file_version_valid.file_name = f"{mock_config_entry.data['prefix']}{valid_backup_core_name}{METADATA_FILE_SUFFIX}"
    mock_file_version_valid.upload_timestamp = 1672531200000  # Jan 1, 2023 00:00:00 UTC
    mock_file_version_valid.file_id = "valid_id"
    # The content is a JSON string of a valid AgentBackup.
    valid_metadata_content = json.dumps(BACKUP_METADATA)
    mock_file_version_valid.download.return_value.response.content = (
        valid_metadata_content.encode("utf-8")
    )

    # 2. Mock for a corrupted metadata file (invalid JSON).
    # Ensure it follows the expected naming convention for metadata files.
    mock_file_version_corrupted = Mock(spec=FileVersion)
    mock_file_version_corrupted.file_name = f"{mock_config_entry.data['prefix']}corrupted_backup_id.tar{METADATA_FILE_SUFFIX}"
    mock_file_version_corrupted.upload_timestamp = 1672531200000
    mock_file_version_corrupted.file_id = "corrupted_id"
    # The content is intentionally malformed JSON.
    mock_file_version_corrupted.download.return_value.response.content = (
        b"{invalid json content"
    )

    # 3. Mock for a non-conforming metadata file (missing 'backup_id').
    # Ensure it follows the expected naming convention for metadata files.
    mock_file_version_non_conforming_missing_id = Mock(spec=FileVersion)
    mock_file_version_non_conforming_missing_id.file_name = f"{mock_config_entry.data['prefix']}non_conforming_missing_id.tar{METADATA_FILE_SUFFIX}"
    mock_file_version_non_conforming_missing_id.upload_timestamp = 1672531200000
    mock_file_version_non_conforming_missing_id.file_id = "non_conforming_id_1"
    # Metadata lacks the 'backup_id' field.
    non_conforming_metadata_1 = {"metadata_version": METADATA_VERSION}
    mock_file_version_non_conforming_missing_id.download.return_value.response.content = json.dumps(
        non_conforming_metadata_1
    ).encode("utf-8")

    # 4. Mock for a non-conforming metadata file (wrong 'metadata_version').
    # Ensure it follows the expected naming convention for metadata files.
    mock_file_version_non_conforming_wrong_version = Mock(spec=FileVersion)
    mock_file_version_non_conforming_wrong_version.file_name = f"{mock_config_entry.data['prefix']}non_conforming_wrong_version.tar{METADATA_FILE_SUFFIX}"
    mock_file_version_non_conforming_wrong_version.upload_timestamp = 1672531200000
    mock_file_version_non_conforming_wrong_version.file_id = "non_conforming_id_2"
    # Metadata has an incorrect 'metadata_version'.
    non_conforming_metadata_2 = {"metadata_version": "2", "backup_id": "test"}
    mock_file_version_non_conforming_wrong_version.download.return_value.response.content = json.dumps(
        non_conforming_metadata_2
    ).encode("utf-8")

    # 5. Mock for a file that causes a B2Error during download.
    # Ensure it follows the expected naming convention for metadata files.
    mock_file_version_b2_error = Mock(spec=FileVersion)
    mock_file_version_b2_error.file_name = (
        f"{mock_config_entry.data['prefix']}b2_error_file.tar{METADATA_FILE_SUFFIX}"
    )
    mock_file_version_b2_error.upload_timestamp = 1672531200000
    mock_file_version_b2_error.file_id = "b2_error_id"
    # Configure the download method to raise a B2Error.
    mock_file_version_b2_error.download.side_effect = B2Error("simulated B2 error")

    # Create the dictionary that _get_all_files_in_prefix should return.
    # This directly controls the input to async_list_backups for file discovery.
    mock_all_files_in_prefix = {
        mock_file_version_valid.file_name: mock_file_version_valid,
        mock_file_version_corrupted.file_name: mock_file_version_corrupted,
        mock_file_version_non_conforming_missing_id.file_name: mock_file_version_non_conforming_missing_id,
        mock_file_version_non_conforming_wrong_version.file_name: mock_file_version_non_conforming_wrong_version,
        mock_file_version_b2_error.file_name: mock_file_version_b2_error,
        mock_file_version_tar.file_name: mock_file_version_tar,
    }

    # --- Patching and Execution ---
    with (
        # Patch _get_all_files_in_prefix directly to control the list of files.
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
            return_value=mock_all_files_in_prefix,
        ),
        # Capture logs at DEBUG level to ensure we catch all relevant messages,
        # including "Skipping non-conforming" which might be at DEBUG or INFO.
        caplog.at_level(logging.DEBUG),
    ):
        # Call the method under test: async_list_backups.
        backups = await agent.async_list_backups()

        # --- Assertions ---
        # Only the valid backup should be returned.
        assert len(backups) == 1
        assert backups[0].backup_id == test_backup.backup_id

        # Assert that specific log messages indicating handling of invalid files are present.
        assert "Failed to parse metadata file" in caplog.text  # For corrupted JSON
        assert (
            "Skipping non-conforming metadata file" in caplog.text
        )  # For missing ID and wrong version
        assert "simulated B2 error" in caplog.text  # For the B2Error during download


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
        # This mock is for when _find_file_and_metadata_version_by_id calls download() on the metadata file
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
    ("patch_target_find", "return_value_find", "expected_status"),
    [
        (
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
            (None, None),
            404,
        ),
    ],
    ids=["backup_not_found"],
)
async def test_agents_download_backup_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    patch_target_find: str,
    return_value_find: tuple,
    expected_status: int,
) -> None:
    """Test agent download backup raises BackupNotFound."""
    with patch(patch_target_find, return_value=return_value_find):
        client = await hass_client()
        backup_id = TEST_BACKUP.backup_id

        resp = await client.get(
            f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
        )
    assert resp.status == expected_status


async def test_agents_upload_simple_file(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent upload backup for a small file using direct async_upload_backup call.

    This test adapts the multipart upload test's structure to verify the simple
    file upload path within the BackblazeBackupAgent.
    """
    client = await hass_client()
    # Define a backup with a size small enough to trigger a simple upload
    backup_with_size = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100})

    # Calculate the expected file name using suggested_filename,
    # which is what BackblazeBackupAgent._upload_simple_b2 will use.
    mock_config_entry.data["prefix"] + suggested_filename(backup_with_size)

    # Create an AsyncMock for the open_stream callable.
    # This mock will simulate reading the backup file in chunks.
    mock_open_stream_callable = AsyncMock()

    # Define an async generator that yields the content for the small file.
    # The total size should match backup_with_size.size (100 bytes here).
    async def async_chunk_generator():
        yield b"test" * 25  # Yields 100 bytes (4 bytes/chunk * 25 chunks)
        # An empty bytes object signals the end of the stream
        yield b""

    mock_open_stream_callable.return_value = async_chunk_generator()

    # Create a mock for the _bucket object, which is part of the Backblaze runtime data.
    mock_bucket = Mock()

    # Create a mock for the FileVersion object that `upload_file` (for simple uploads)
    # is expected to return.
    mock_file_version_result = Mock(spec=FileVersion)
    mock_file_version_result.id_ = "test_simple_file_id_456"  # Assign a dummy ID

    # Set the return value for the `upload_file` method on `mock_bucket`.
    # This is the method called for simple (non-multipart) uploads.
    mock_bucket.upload_file.return_value = mock_file_version_result

    with (
        # Patch BackupManager.async_get_backup to return our test backup.
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=backup_with_size,
        ),
        # Patch read_backup to return our test backup.
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=backup_with_size,
        ),
        # Patch the `runtime_data` attribute of the `mock_config_entry` instance
        # to inject our mock_bucket.
        patch.object(mock_config_entry, "runtime_data", new=mock_bucket),
        # Patch _upload_multipart_b2 to ensure it's *not* called, confirming the simple path.
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_multipart_b2",
            autospec=True,
        ) as mock_upload_multipart_b2,
        # Capture INFO level logs to check for the success message.
        caplog.at_level(logging.INFO),
    ):
        # Instantiate the BackblazeBackupAgent directly.
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        # Call the async_upload_backup method directly, simulating the upload process.
        await agent.async_upload_backup(
            open_stream=mock_open_stream_callable,
            backup=backup_with_size,
        )

    # Assert that the multipart upload path was not taken.
    assert mock_upload_multipart_b2.called is False

    # Assert that the `upload_file` method on the mock_bucket was called exactly once.
    assert mock_bucket.upload_bytes.call_count == 2

    # Construct the expected log message using the calculated file name and mock ID.
    expected_log_message = "Simple upload finished for "
    # Assert that the expected log message is present in the captured logs.
    assert expected_log_message in caplog.text


async def test_agents_upload_multipart_file(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent upload backup for a large file using multipart upload."""
    client = await hass_client()
    backup_with_size = AgentBackup(
        **{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 1.05}
    )

    # Calculate the expected file name using suggested_filename
    # This is the name that BackblazeBackupAgent._upload_multipart_b2 will use
    expected_b2_file_name = mock_config_entry.data["prefix"] + suggested_filename(
        backup_with_size
    )

    mock_open_stream_callable = AsyncMock()

    async def async_chunk_generator():
        yield b"test" * DEFAULT_MIN_PART_SIZE
        yield b"test" * (int(DEFAULT_MIN_PART_SIZE * 0.05))

    mock_open_stream_callable.return_value = async_chunk_generator()

    # Create a mock for the _bucket object.
    mock_bucket = Mock()

    # Create a mock for the FileVersion object that `upload_local_file` should return.
    mock_file_version_result = Mock()
    mock_file_version_result.id_ = "test_file_id_123"  # Assign a dummy ID

    # Set the return value for the `upload_local_file` method on `mock_bucket`.
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
        # Patch the `runtime_data` attribute of the `mock_config_entry` instance.
        patch.object(mock_config_entry, "runtime_data", new=mock_bucket),
        # Patch _upload_simple_b2 to ensure the multipart path is taken.
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_simple_b2",
            autospec=True,
        ) as mock_upload_simple_b2,
        caplog.at_level(logging.INFO),
    ):
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        await agent.async_upload_backup(
            open_stream=mock_open_stream_callable,
            backup=backup_with_size,
        )

    assert mock_upload_simple_b2.called is False  # Ensure simple upload was not called
    mock_bucket.upload_local_file.assert_called_once()  # Assert on the mock_bucket's method

    # Assert arguments passed to upload_local_file using the calculated name
    call_args, call_kwargs = mock_bucket.upload_local_file.call_args
    assert "local_file" in call_kwargs
    assert call_kwargs["file_name"] == expected_b2_file_name  # Use calculated name here
    assert call_kwargs["content_type"] is not None
    assert "file_info" in call_kwargs

    # The `caplog` assertion should now correctly find the log message with the mock ID and calculated file name.
    expected_log_message = (
        f"Successfully uploaded "
        f"{expected_b2_file_name} "  # Use calculated name here
        f"(ID: {mock_file_version_result.id_})"
    )
    assert expected_log_message in caplog.text


async def test_agents_upload_failure_and_abort(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent upload backup for various failure scenarios including multipart abort."""
    client = await hass_client()

    # Scenario 1: Multipart upload fails and should be aborted
    backup_multipart_fail = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100000000})
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=backup_multipart_fail,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=backup_multipart_fail,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_multipart_b2",
            side_effect=Exception("Simulated multipart upload error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test" * 100000, b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": io.StringIO("test")},
        )
    assert resp.status == 201
    assert "Upload failed for backblaze" in caplog.text
    assert "Simulated multipart upload error" in caplog.text

    caplog.clear()

    # Scenario 2: Metadata upload fails
    backup_metadata_fail = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100})
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=backup_metadata_fail,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=backup_metadata_fail,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent.async_upload_backup",
            side_effect=BackupAgentError("Failed during upload_files"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": io.StringIO("test")},
        )
    assert resp.status == 201
    assert "Failed during upload_files" in caplog.text

    caplog.clear()

    # Scenario 3: Unexpected error during upload
    backup_unexpected_error = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100})
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=backup_unexpected_error,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=backup_unexpected_error,
        ),
        patch("pathlib.Path.open") as mocked_open,
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._upload_simple_b2",
            side_effect=ValueError("Simulated unexpected error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": io.StringIO("test")},
        )
    assert resp.status == 201
    assert "An unexpected error occurred during backup upload" in caplog.text
    assert "Simulated unexpected error" in caplog.text


async def test_upload_metadata_failure_cleanup(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test cleanup when metadata upload fails after successful backup upload."""
    client = await hass_client()
    # Create a backup with small size to trigger simple upload
    backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": 100})

    # Mock bucket and file version
    mock_bucket = Mock()
    mock_file_version = Mock()
    mock_bucket.upload_bytes.return_value = mock_file_version

    # Make metadata upload fail
    mock_bucket.upload_bytes.side_effect = [
        mock_file_version,  # Success for backup file
        B2Error("Metadata upload failed"),  # Failure for metadata
    ]

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
        ),  # Ensure multipart isn't used
        caplog.at_level(logging.WARNING),
    ):
        # Create an AsyncMock for the open_stream callable
        mock_open_stream_callable = AsyncMock()

        async def async_chunk_generator():
            yield b"test"
            yield b""

        mock_open_stream_callable.return_value = async_chunk_generator()

        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        # This should trigger the cleanup logic
        with pytest.raises(BackupAgentError):
            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable,
                backup=backup,
            )

        # Verify cleanup was attempted - mock the file info lookup
        mock_bucket.get_file_info_by_name.assert_called_once()
        # The delete method should be called on the file version
        mock_bucket.get_file_info_by_name.return_value.delete.assert_called_once()
        assert "Attempting to delete partially uploaded main backup file" in caplog.text
        assert "Metadata upload failed" in caplog.text


async def test_stream_closing_behavior(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that streams are properly closed during multipart upload."""
    client = await hass_client()
    backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2})

    class MockStreamClose:
        def __init__(self) -> None:
            self.close_called = False

        async def __aiter__(self):
            yield b"chunk1"
            yield b"chunk2"

        def close(self):
            self.close_called = True

        # Add async context manager methods
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

        # Add async context manager methods
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self.aclose()

    stream_with_close = MockStreamClose()
    stream_with_aclose = MockStreamAclose()

    # mock_open_stream_callable should return the async context manager instances directly
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
        patch(
            "homeassistant.components.backblaze.backup.aiofiles.open"
        ),  # Bypass actual file ops
    ):
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        # Now, open_stream=mock_open_stream_callable works directly because
        # mock_open_stream_callable() returns an object that is an async context manager.
        await agent.async_upload_backup(
            open_stream=mock_open_stream_callable,
            backup=backup,
        )
        assert stream_with_close.close_called

        await agent.async_upload_backup(
            open_stream=mock_open_stream_callable,
            backup=backup,
        )
        assert stream_with_aclose.aclose_called


async def test_download_backup_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test BackupNotFound exception during backup download."""
    client = await hass_client()
    agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

    with (
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
            return_value=(None, None),
        ),
    ):
        # Create a dummy async generator for the stream
        async def dummy_stream():
            yield b""

        with pytest.raises(BackupNotFound, match="Backup test_backup not found"):
            await agent.async_download_backup("test_backup", stream=dummy_stream())


async def test_upload_multipart_b2_exceptions(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling in multipart upload."""
    client = await hass_client()
    backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2})

    mock_open_stream_callable = AsyncMock()

    async def async_chunk_generator():
        yield b"chunk1"
        yield b"chunk2"

    mock_open_stream_callable.return_value = async_chunk_generator()

    # Case 1: B2Error during upload
    with (
        patch.object(mock_config_entry, "runtime_data", new=Mock()),
        patch(
            "homeassistant.components.backblaze.backup.aiofiles.open",
            side_effect=B2Error("B2 connection error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        with pytest.raises(BackupAgentError):
            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable,
                backup=backup,
            )

        assert "B2 connection error during upload" in caplog.text

    caplog.clear()

    # Case 2: Unexpected exception during upload
    with (
        patch.object(mock_config_entry, "runtime_data", new=Mock()),
        patch(
            "homeassistant.components.backblaze.backup.aiofiles.open",
            side_effect=Exception("Unexpected error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        with pytest.raises(BackupAgentError):
            await agent.async_upload_backup(
                open_stream=mock_open_stream_callable,
                backup=backup,
            )

        assert "An error occurred during upload" in caplog.text


async def test_temp_file_cleanup_failure(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test temporary file cleanup failure during multipart upload."""
    client = await hass_client()
    backup = AgentBackup(**{**TEST_BACKUP.as_dict(), "size": DEFAULT_MIN_PART_SIZE * 2})

    mock_open_stream_callable = AsyncMock()

    async def async_chunk_generator():
        yield b"chunk1"
        yield b"chunk2"

    mock_open_stream_callable.return_value = async_chunk_generator()

    mock_bucket = Mock()
    with (
        patch.object(mock_config_entry, "runtime_data", new=mock_bucket),
        patch(
            "homeassistant.components.backblaze.backup.aiofiles.open"
        ),  # Bypass actual file ops
        patch("os.unlink", side_effect=OSError("Permission denied")),
        caplog.at_level(logging.WARNING),
    ):
        agent = BackblazeBackupAgent(client.app["hass"], mock_config_entry)

        # Mock the upload to succeed so we reach the cleanup step
        mock_bucket.upload_local_file.return_value = Mock()

        await agent.async_upload_backup(
            open_stream=mock_open_stream_callable,
            backup=backup,
        )

        assert any(
            "Failed to delete temporary file" in record.message
            for record in caplog.records
        )


async def test_metadata_deletion_unexpected_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unexpected exceptions during metadata deletion."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    # Setup mock files
    mock_backup_file = Mock(spec=FileVersion)
    mock_metadata_file = Mock(spec=FileVersion)

    # Make metadata deletion raise an unexpected exception
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

        # Verify the backup file was still deleted
        mock_backup_file.delete.assert_called_once()

        # Verify the error was logged
        assert "Unexpected error from executor for metadata" in caplog.text


async def test_debug_log_backup_not_found(
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
        # This will call _find_file_and_metadata_version_by_id which should log at debug
        with pytest.raises(BackupNotFound):
            await agent.async_get_backup("non_existent_backup")

        assert "Backup non_existent_backup not found" in caplog.text


async def test_metadata_processing_backup_file_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test warning when metadata file exists but backup file is missing."""
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    # Create mock metadata file
    mock_metadata_file = Mock(spec=FileVersion)
    mock_metadata_file.file_name = (
        f"{mock_config_entry.data['prefix']}test_backup.tar{METADATA_FILE_SUFFIX}"
    )

    # Mock metadata content
    def mock_download():
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "metadata_version": METADATA_VERSION,
                "backup_id": "test_backup",
                "backup_metadata": TEST_BACKUP.as_dict(),
            }
        ).encode("utf-8")
        return mock_response

    mock_metadata_file.download.return_value.response = mock_download()

    # Return only the metadata file in the file list
    with patch(
        "homeassistant.components.backblaze.backup.BackblazeBackupAgent._get_all_files_in_prefix",
        return_value={mock_metadata_file.file_name: mock_metadata_file},
    ):
        # This will call _process_metadata_file_for_id_sync
        result = await agent.async_list_backups()

        # Should not return the backup since file is missing
        assert len(result) == 0
        assert "no corresponding backup file" in caplog.text


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
) -> None:
    """Test agent delete backup."""
    # Mock _find_file_and_metadata_version_by_id to return valid file versions for deletion
    mock_backup_file = Mock(
        file_name=f"{test_backup.backup_id}.tar", file_id="backup_file_id"
    )
    mock_metadata_file = Mock(
        file_name=f"{test_backup.backup_id}.metadata.json", file_id="metadata_file_id"
    )

    # 1. Initialize MagicMock for the delete method on your mock objects
    mock_backup_file.delete = MagicMock()
    mock_metadata_file.delete = MagicMock()

    with (
        patch(
            "homeassistant.components.backblaze.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
            return_value=(mock_backup_file, mock_metadata_file),
        ),
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
    (
        "find_file_return_value",
        "delete_side_effect",
        "expected_agent_error_in_response",
    ),
    [
        # Scenario 1: Metadata file not found during delete
        # Main backup file deleted, warning logged for missing metadata.
        # API response indicates success with no agent errors.
        (
            (Mock(spec=FileVersion, file_name="test.tar"), None),
            None,
            False,
        ),
        # Scenario 2: B2Error during metadata file deletion
        # Main backup file deleted, but metadata deletion fails with B2Error.
        # This is converted to BackupAgentError, causing an agent error in the API response.
        (
            (
                Mock(spec=FileVersion, file_name="test.tar"),
                Mock(spec=FileVersion, file_name="test.tar.metadata.json"),
            ),
            B2Error("test b2 error during metadata delete"),
            True,
        ),
        # Scenario 3: Backup not found
        # _find_file_and_metadata_version_by_id returns None,None.
        # BackupNotFound is raised and handled by Home Assistant core,
        # resulting in a successful API response with no agent errors.
        (
            (None, None),
            None,
            False,
        ),
    ],
    ids=[
        "metadata_not_found",
        "b2_error_on_metadata_delete",
        "backup_not_found_no_delete_calls",
    ],
)
async def test_agents_delete_scenarios(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    find_file_return_value: tuple[FileVersion | None, FileVersion | None],
    delete_side_effect: Exception | None,
    expected_agent_error_in_response: bool,
) -> None:
    """Test agent delete backup for various scenarios."""

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

    # The API generally returns success=True for the request itself,
    # and communicates agent-specific errors via the 'agent_errors' field.
    assert response["success"] is True

    if expected_agent_error_in_response:
        expected_response_error_msg = "Failed during async_delete_backup"
        assert response["result"] == {
            "agent_errors": {
                f"{agent.domain}.{agent.unique_id}": expected_response_error_msg
            }
        }
        # Verify specific error message from B2Error is in logs.
        assert any(
            "Failed to delete metadata file" in s and str(delete_side_effect) in s
            for s in caplog.messages
        )
        assert mock_main_file_delete.call_count == 1
        assert mock_metadata_file_delete.call_count == 1
    else:
        assert response["result"] == {"agent_errors": {}}
        # For "metadata_not_found" scenario, a warning should be logged.
        assert any(
            "Metadata file for backup" in s and "not found for deletion" in s
            for s in caplog.messages
        )
        assert mock_main_file_delete.call_count == 1
        assert mock_metadata_file_delete.call_count == 0


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
