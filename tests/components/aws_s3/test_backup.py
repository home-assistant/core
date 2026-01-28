"""Test the AWS S3 backup platform."""

from collections.abc import AsyncGenerator
from io import StringIO
import json
from time import time
from unittest.mock import AsyncMock, Mock, patch

from botocore.exceptions import ConnectTimeoutError
import pytest

from homeassistant.components.aws_s3.backup import (
    MULTIPART_MIN_PART_SIZE_BYTES,
    BotoCoreError,
    S3BackupAgent,
    async_register_backup_agents_listener,
    suggested_filenames,
)
from homeassistant.components.aws_s3.const import (
    CONF_ENDPOINT_URL,
    CONF_PREFIX,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import USER_INPUT

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, MagicMock, WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up S3 integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
        await setup_integration(hass, mock_config_entry)

        await hass.async_block_till_done()
        yield


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
    tar_filename, metadata_filename = suggested_filenames(backup)

    assert tar_filename == "my_pretty_backup_2021-01-01_01.02_03000000.tar"
    assert (
        metadata_filename == "my_pretty_backup_2021-01-01_01.02_03000000.metadata.json"
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
    test_backup: AgentBackup,
) -> None:
    """Test agent list backups."""

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": test_backup.addons,
            "agents": {
                f"{DOMAIN}.{mock_config_entry.entry_id}": {
                    "protected": test_backup.protected,
                    "size": test_backup.size,
                }
            },
            "backup_id": test_backup.backup_id,
            "database_included": test_backup.database_included,
            "date": test_backup.date,
            "extra_metadata": test_backup.extra_metadata,
            "failed_addons": [],
            "failed_agent_ids": [],
            "failed_folders": [],
            "folders": test_backup.folders,
            "homeassistant_included": test_backup.homeassistant_included,
            "homeassistant_version": test_backup.homeassistant_version,
            "name": test_backup.name,
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
        "addons": test_backup.addons,
        "agents": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": {
                "protected": test_backup.protected,
                "size": test_backup.size,
            }
        },
        "backup_id": test_backup.backup_id,
        "database_included": test_backup.database_included,
        "date": test_backup.date,
        "extra_metadata": test_backup.extra_metadata,
        "failed_addons": [],
        "failed_agent_ids": [],
        "failed_folders": [],
        "folders": test_backup.folders,
        "homeassistant_included": test_backup.homeassistant_included,
        "homeassistant_version": test_backup.homeassistant_version,
        "name": test_backup.name,
        "with_automatic_settings": None,
    }


async def test_agents_get_backup_does_not_throw_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Test agent get backup does not throw on a backup not found."""
    mock_client.list_objects_v2.return_value = {"Contents": []}

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": "random"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] is None


async def test_agents_list_backups_with_corrupted_metadata(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    test_backup: AgentBackup,
) -> None:
    """Test listing backups when one metadata file is corrupted."""
    # Create agent
    agent = S3BackupAgent(hass, mock_config_entry)

    # Set up mock responses for both valid and corrupted metadata files
    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "valid_backup.metadata.json",
                "LastModified": "2023-01-01T00:00:00+00:00",
            },
            {
                "Key": "corrupted_backup.metadata.json",
                "LastModified": "2023-01-01T00:00:00+00:00",
            },
        ]
    }

    # Mock responses for get_object calls
    valid_metadata = json.dumps(test_backup.as_dict())
    corrupted_metadata = "{invalid json content"

    async def mock_get_object(**kwargs):
        """Mock get_object with different responses based on the key."""
        key = kwargs.get("Key", "")
        if "valid_backup" in key:
            mock_body = AsyncMock()
            mock_body.read.return_value = valid_metadata.encode()
            return {"Body": mock_body}
        # Corrupted metadata
        mock_body = AsyncMock()
        mock_body.read.return_value = corrupted_metadata.encode()
        return {"Body": mock_body}

    mock_client.get_object.side_effect = mock_get_object

    backups = await agent.async_list_backups()
    assert len(backups) == 1
    assert backups[0].backup_id == test_backup.backup_id
    assert "Failed to process metadata file" in caplog.text


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Test agent delete backup."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": "23e64aec",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    # Should delete both the tar and the metadata file
    assert mock_client.delete_object.call_count == 2


async def test_agents_delete_not_throwing_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Test agent delete backup does not throw on a backup not found."""
    mock_client.list_objects_v2.return_value = {"Contents": []}

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": "random",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    assert mock_client.delete_object.call_count == 0


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=test_backup,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        # we must emit at least two chunks
        # the "appendix" chunk triggers the upload of the final buffer part
        mocked_open.return_value.read = Mock(
            side_effect=[
                b"a" * test_backup.size,
                b"appendix",
                b"",
            ]
        )
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

        assert resp.status == 201
        assert f"Uploading backup {test_backup.backup_id}" in caplog.text
        if test_backup.size < MULTIPART_MIN_PART_SIZE_BYTES:
            # single part + metadata both as regular upload (no multiparts)
            assert mock_client.create_multipart_upload.await_count == 0
            assert mock_client.put_object.await_count == 2
        else:
            assert "Uploading final part" in caplog.text
            # 2 parts as multipart + metadata as regular upload
            assert mock_client.create_multipart_upload.await_count == 1
            assert mock_client.upload_part.await_count == 2
            assert mock_client.complete_multipart_upload.await_count == 1
            assert mock_client.put_object.await_count == 1


async def test_agents_upload_network_failure(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
) -> None:
    """Test agent upload backup with network failure."""
    client = await hass_client()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=test_backup,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=test_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        # simulate network failure
        mock_client.put_object.side_effect = mock_client.upload_part.side_effect = (
            mock_client.abort_multipart_upload.side_effect
        ) = ConnectTimeoutError(endpoint_url=USER_INPUT[CONF_ENDPOINT_URL])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert "Upload failed for aws_s3" in caplog.text


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    backup_id = "23e64aec"

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
    assert mock_client.get_object.call_count == 2  # One for metadata, one for tar file


async def test_error_during_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
) -> None:
    """Test the error wrapper."""
    mock_client.delete_object.side_effect = BotoCoreError

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": test_backup.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": "Failed during async_delete_backup"
        }
    }


async def test_cache_expiration(
    hass: HomeAssistant,
    mock_client: MagicMock,
    test_backup: AgentBackup,
) -> None:
    """Test that the cache expires correctly."""
    # Mock the entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"bucket": "test-bucket", "prefix": "test/"},
        unique_id="test-unique-id",
        title="Test S3",
    )
    mock_entry.runtime_data = mock_client

    # Create agent
    agent = S3BackupAgent(hass, mock_entry)

    # Mock metadata response
    metadata_content = json.dumps(test_backup.as_dict())
    mock_body = AsyncMock()
    mock_body.read.return_value = metadata_content.encode()
    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "test.metadata.json", "LastModified": "2023-01-01T00:00:00+00:00"}
        ]
    }

    # First call should query S3
    await agent.async_list_backups()
    assert mock_client.list_objects_v2.call_count == 1
    assert mock_client.get_object.call_count == 1

    # Second call should use cache
    await agent.async_list_backups()
    assert mock_client.list_objects_v2.call_count == 1
    assert mock_client.get_object.call_count == 1

    # Set cache to expire
    agent._cache_expiration = time() - 1

    # Third call should query S3 again
    await agent.async_list_backups()
    assert mock_client.list_objects_v2.call_count == 2
    assert mock_client.get_object.call_count == 2


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [
        listener
    ]  # make sure it's the last listener
    remove_listener()

    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data


async def test_prefix_used_in_api_calls(
    hass: HomeAssistant,
    mock_client: MagicMock,
    test_backup: AgentBackup,
) -> None:
    """Test that prefix is correctly used in all S3 API calls."""
    # Create config entry with prefix
    prefix = "backups/homeassistant/"
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"bucket": "test-bucket", CONF_PREFIX: prefix},
        unique_id="test-unique-id",
        title="Test S3",
    )
    mock_entry.runtime_data = mock_client

    # Create agent
    agent = S3BackupAgent(hass, mock_entry)

    # Mock backup filenames
    tar_filename, metadata_filename = suggested_filenames(test_backup)
    expected_tar_key = f"{prefix}{tar_filename}"
    expected_metadata_key = f"{prefix}{metadata_filename}"

    # Test list_objects_v2 uses prefix
    mock_client.list_objects_v2.return_value = {"Contents": []}
    await agent.async_list_backups()

    mock_client.list_objects_v2.assert_called_with(
        Bucket="test-bucket",
        Prefix=prefix,
    )

    # Test upload uses prefix in put_object calls
    mock_backup_data = b"test backup data"
    await agent.async_upload_backup(test_backup, lambda: [mock_backup_data])

    # Check that put_object was called with prefixed keys
    put_object_calls = mock_client.put_object.call_args_list
    assert len(put_object_calls) >= 2  # At least tar and metadata files

    # Find the metadata and tar file calls
    metadata_call = None
    tar_call = None
    for call in put_object_calls:
        key = call[1]["Key"]  # Get the Key parameter
        if key == expected_metadata_key:
            metadata_call = call
        elif key == expected_tar_key:
            tar_call = call

    assert metadata_call is not None, f"Metadata call with key {expected_metadata_key} not found"
    assert tar_call is not None, f"Tar call with key {expected_tar_key} not found"

    # Test download uses prefix
    mock_body = AsyncMock()
    mock_body.iter_chunks.return_value = [b"backup data"]
    mock_client.get_object.return_value = {"Body": mock_body}

    async for _ in await agent.async_download_backup(test_backup.backup_id):
        pass

    mock_client.get_object.assert_called_with(
        Bucket="test-bucket",
        Key=expected_tar_key,
    )

    # Test delete uses prefix
    await agent.async_delete_backup(test_backup.backup_id)

    delete_calls = mock_client.delete_object.call_args_list
    assert len(delete_calls) == 2  # Should delete both tar and metadata files

    deleted_keys = {call[1]["Key"] for call in delete_calls}
    assert expected_tar_key in deleted_keys
    assert expected_metadata_key in deleted_keys


async def test_backward_compatibility_no_prefix(
    hass: HomeAssistant,
    mock_client: MagicMock,
    test_backup: AgentBackup,
) -> None:
    """Test that old config entries without prefix still work."""
    # Create config entry without prefix (simulating old config)
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"bucket": "test-bucket"},  # No CONF_PREFIX key
        unique_id="test-unique-id",
        title="Test S3",
    )
    mock_entry.runtime_data = mock_client

    # Create agent - should work without errors
    agent = S3BackupAgent(hass, mock_entry)

    # Verify prefix defaults to empty string
    assert agent._prefix == ""

    # Mock backup filenames
    tar_filename, metadata_filename = suggested_filenames(test_backup)

    # Test list_objects_v2 works without prefix
    mock_client.list_objects_v2.return_value = {"Contents": []}
    await agent.async_list_backups()

    mock_client.list_objects_v2.assert_called_with(
        Bucket="test-bucket",
        Prefix="",  # Empty prefix
    )

    # Test upload works without prefix
    mock_backup_data = b"test backup data"
    await agent.async_upload_backup(test_backup, lambda: [mock_backup_data])

    # Check that put_object was called with non-prefixed keys
    put_object_calls = mock_client.put_object.call_args_list
    keys_used = {call[1]["Key"] for call in put_object_calls}
    assert tar_filename in keys_used
    assert metadata_filename in keys_used


async def test_empty_prefix_behavior(
    hass: HomeAssistant,
    mock_client: MagicMock,
    test_backup: AgentBackup,
) -> None:
    """Test that empty prefix string behaves the same as no prefix."""
    # Create config entry with empty prefix
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"bucket": "test-bucket", CONF_PREFIX: ""},
        unique_id="test-unique-id",
        title="Test S3",
    )
    mock_entry.runtime_data = mock_client

    # Create agent
    agent = S3BackupAgent(hass, mock_entry)

    # Verify prefix is empty string
    assert agent._prefix == ""

    # Mock backup filenames
    tar_filename, metadata_filename = suggested_filenames(test_backup)

    # Test that _add_prefix with empty prefix returns original key
    assert agent._add_prefix(tar_filename) == tar_filename
    assert agent._add_prefix(metadata_filename) == metadata_filename

    # Test list_objects_v2 works with empty prefix
    mock_client.list_objects_v2.return_value = {"Contents": []}
    await agent.async_list_backups()

    mock_client.list_objects_v2.assert_called_with(
        Bucket="test-bucket",
        Prefix="",
    )


async def test_prefix_add_prefix_method(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test the _add_prefix method behavior with different prefixes."""
    # Test with trailing slash prefix
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"bucket": "test-bucket", CONF_PREFIX: "backups/"},
        unique_id="test-unique-id",
        title="Test S3",
    )
    mock_entry.runtime_data = mock_client
    agent = S3BackupAgent(hass, mock_entry)

    assert agent._add_prefix("file.tar") == "backups/file.tar"

    # Test with no trailing slash prefix
    mock_entry.data[CONF_PREFIX] = "backups"
    agent = S3BackupAgent(hass, mock_entry)

    assert agent._add_prefix("file.tar") == "backupsfile.tar"

    # Test with complex prefix
    mock_entry.data[CONF_PREFIX] = "my-org/homeassistant/prod/"
    agent = S3BackupAgent(hass, mock_entry)

    assert agent._add_prefix("file.tar") == "my-org/homeassistant/prod/file.tar"
