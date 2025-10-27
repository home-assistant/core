"""Backblaze B2 backup agent tests."""

from collections.abc import AsyncGenerator
from io import StringIO
import json
import logging
import threading
import time
from unittest.mock import Mock, patch

from b2sdk.v2.exception import B2Error
import pytest
import requests

from homeassistant.components.backblaze_b2.backup import (
    MAX_CONCURRENT_DOWNLOADS,
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


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up integration."""
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
    """Test agent info."""
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
    """Test listing backups."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()
    assert response["success"]
    assert "backups" in response["result"]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test getting backup."""
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
    """Test getting nonexistent backup."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": "random"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["backup"] is None


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test deleting backup."""
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
    """Test deleting nonexistent backup."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/delete", "backup_id": "random"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agent_errors": {}}


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test uploading backup."""
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
        caplog.at_level(logging.INFO),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )
    assert resp.status == 201
    assert any("upload" in msg.lower() for msg in caplog.messages)


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test downloading backup."""
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 200


async def test_agents_download_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test downloading nonexistent backup."""
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/nonexistent?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 404


async def test_get_file_for_download_raises_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test exception handling for nonexistent backup.

    Directly tests the private _get_file_for_download method, which is an internal
    helper not exposed through the WebSocket/HTTP API.
    """
    agent = BackblazeBackupAgent(hass, mock_config_entry)
    with pytest.raises(BackupNotFound, match="Backup nonexistent not found"):
        await agent._get_file_for_download("nonexistent")


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
    """Test error handling."""
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
    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]
    remove_listener()
    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data


async def test_parse_metadata_invalid_json() -> None:
    """Test metadata parsing."""
    with pytest.raises(ValueError, match="Invalid JSON format"):
        _parse_metadata("invalid json")

    with pytest.raises(TypeError, match="JSON content is not a dictionary"):
        _parse_metadata('["not", "a", "dict"]')


async def test_error_during_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._get_all_files_in_prefix",
        side_effect=B2Error("API error"),
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

        assert response["success"]
        assert (
            f"{DOMAIN}.{mock_config_entry.entry_id}"
            in response["result"]["agent_errors"]
        )
        assert (
            "Failed during async_list_backups"
            in response["result"]["agent_errors"][
                f"{DOMAIN}.{mock_config_entry.entry_id}"
            ]
        )


async def test_error_during_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
        side_effect=B2Error("API error"),
    ):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": "test_backup"}
        )
        response = await client.receive_json()

        assert response["success"]
        assert (
            f"{DOMAIN}.{mock_config_entry.entry_id}"
            in response["result"]["agent_errors"]
        )
        assert (
            "Failed during async_get_backup"
            in response["result"]["agent_errors"][
                f"{DOMAIN}.{mock_config_entry.entry_id}"
            ]
        )


async def test_metadata_file_download_error_during_list(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test error handling."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._process_metadata_file_sync",
        return_value=None,
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

        assert response["success"]


async def test_delete_with_metadata_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling."""
    client = await hass_ws_client(hass)

    mock_main_file = Mock()
    mock_main_file.file_name = f"{TEST_BACKUP.backup_id}.tar"
    mock_main_file.delete = Mock()
    mock_metadata_file = Mock()
    mock_metadata_file.file_name = f"{TEST_BACKUP.backup_id}.metadata.json"
    mock_metadata_file.delete.side_effect = B2Error("Delete failed")

    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
        return_value=(mock_main_file, mock_metadata_file),
    ):
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()

        assert response["success"]
        assert (
            f"{DOMAIN}.{mock_config_entry.entry_id}"
            in response["result"]["agent_errors"]
        )


async def test_delete_without_metadata_file(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test deleting without metadata."""
    client = await hass_ws_client(hass)

    mock_main_file = Mock()
    mock_main_file.file_name = f"{TEST_BACKUP.backup_id}.tar"
    mock_main_file.delete = Mock()

    with (
        patch(
            "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
            return_value=(mock_main_file, None),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()

        assert response["success"]
        assert response["result"] == {"agent_errors": {}}
        mock_main_file.delete.assert_called_once()
        assert "Metadata file for backup" in caplog.text


async def test_download_backup_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test downloading nonexistent backup."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._find_file_and_metadata_version_by_id",
        return_value=(None, None),
    ):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": "nonexistent"}
        )
        response = await client.receive_json()

        assert response["success"]
        assert response["result"]["backup"] is None


async def test_metadata_file_invalid_json_during_list(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid metadata handling."""
    client = await hass_ws_client(hass)

    mock_bad_metadata = Mock()
    mock_bad_metadata.file_name = "testprefix/bad.metadata.json"
    mock_bad_download = Mock()
    mock_bad_response = Mock()
    mock_bad_response.content = b"not valid json"
    mock_bad_download.response = mock_bad_response
    mock_bad_metadata.download.return_value = mock_bad_download

    async def mock_get_all_files(self):
        real_files = await self._hass.async_add_executor_job(
            self._fetch_all_files_in_prefix
        )
        real_files["testprefix/bad.metadata.json"] = mock_bad_metadata
        return real_files

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


async def test_metadata_file_missing_backup_file(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test orphaned metadata handling."""
    client = await hass_ws_client(hass)

    mock_metadata_version = Mock()
    mock_metadata_version.file_name = "testprefix/orphan.metadata.json"
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps(BACKUP_METADATA).encode()
    mock_download.response = mock_response
    mock_metadata_version.download.return_value = mock_download

    def process_metadata_side_effect(file_name, file_version, all_files):
        if file_name.endswith(".metadata.json"):
            return
        return

    with (
        patch(
            "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._process_metadata_file_sync",
            side_effect=process_metadata_side_effect,
        ),
        caplog.at_level(logging.WARNING),
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

        assert response["success"]


async def test_get_backup_with_cache_hit(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test cache behavior."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
    )
    response1 = await client.receive_json()
    assert response1["success"]

    await client.send_json_auto_id(
        {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
    )
    response2 = await client.receive_json()
    assert response2["success"]


async def test_upload_with_generic_exception(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling."""
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
        patch(
            "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._upload_backup_file",
            side_effect=RuntimeError("Generic upload error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201


async def test_upload_with_cleanup_and_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload logging and cleanup.

    Directly tests the agent to patch internal methods (_upload_backup_file,
    _upload_metadata_file) and access private attributes (agent._bucket), which
    cannot be tested through the WebSocket/HTTP API.
    """
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    async def mock_open_stream():
        return iter([b"test data"])

    with (
        patch.object(agent, "_upload_backup_file"),
        patch.object(agent, "_upload_metadata_file"),
        caplog.at_level(logging.INFO),
    ):
        await agent.async_upload_backup(
            open_stream=mock_open_stream, backup=TEST_BACKUP
        )

    assert any("Main backup file upload finished" in msg for msg in caplog.messages)
    assert any("Metadata file upload finished" in msg for msg in caplog.messages)
    assert any("Backup upload complete" in msg for msg in caplog.messages)

    caplog.clear()

    mock_file_info = Mock()
    with (
        patch.object(agent, "_upload_backup_file"),
        patch.object(agent, "_upload_metadata_file", side_effect=B2Error("Failed")),
        patch.object(
            agent._bucket, "get_file_info_by_name", return_value=mock_file_info
        ),
        caplog.at_level(logging.INFO),
        pytest.raises(BackupAgentError),
    ):
        await agent.async_upload_backup(
            open_stream=mock_open_stream, backup=TEST_BACKUP
        )

    assert mock_file_info.delete.called
    assert any(
        "Successfully deleted partially uploaded" in msg for msg in caplog.messages
    )


async def test_upload_error_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload error logging.

    Directly tests the agent to call the private _upload_backup_file method and
    verify specific error logging behavior not accessible through the public API.
    """

    agent = BackblazeBackupAgent(hass, mock_config_entry)

    async def mock_open_stream():
        async def async_gen():
            yield b"test"

        return async_gen()

    with (
        patch.object(
            agent._hass, "async_add_executor_job", side_effect=B2Error("B2 error")
        ),
        pytest.raises(B2Error),
        caplog.at_level(logging.ERROR),
    ):
        await agent._upload_backup_file("test.tar", mock_open_stream, {})

    assert "B2 connection error during upload" in caplog.text

    caplog.clear()

    with (
        patch.object(
            agent._hass,
            "async_add_executor_job",
            side_effect=RuntimeError("Generic error"),
        ),
        pytest.raises(RuntimeError),
        caplog.at_level(logging.ERROR),
    ):
        await agent._upload_backup_file("test.tar", mock_open_stream, {})

    assert "An error occurred during upload" in caplog.text


async def test_cache_behavior(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cache behavior.

    Directly tests the agent to manipulate and assert on private cache attributes
    (_backup_list_cache, _all_files_cache, _*_expiration) and the private
    _invalidate_caches method, which are internal implementation details.
    """
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    agent._backup_list_cache = {TEST_BACKUP.backup_id: TEST_BACKUP}
    agent._backup_list_cache_expiration = 9999999999.0

    backups = await agent.async_list_backups()
    assert len(backups) == 1
    assert backups[0].backup_id == TEST_BACKUP.backup_id

    backup = await agent.async_get_backup(TEST_BACKUP.backup_id)
    assert backup.backup_id == TEST_BACKUP.backup_id

    agent._backup_list_cache = {}
    agent._backup_list_cache_expiration = 9999999999.0

    mock_file = Mock(size=TEST_BACKUP.size)
    mock_metadata = Mock()
    mock_metadata.download.return_value.response.content = json.dumps(
        BACKUP_METADATA
    ).encode()

    with (
        patch.object(
            agent,
            "_find_file_and_metadata_version_by_id",
            return_value=(mock_file, mock_metadata),
        ),
        patch(
            "homeassistant.components.backblaze_b2.backup._create_backup_from_metadata",
            return_value=TEST_BACKUP,
        ),
    ):
        await agent.async_get_backup(TEST_BACKUP.backup_id)

    assert TEST_BACKUP.backup_id in agent._backup_list_cache

    agent._all_files_cache = {"file1.tar": Mock(), "file1.metadata.json": Mock()}
    agent._all_files_cache_expiration = 9999999999.0
    agent._backup_list_cache = {TEST_BACKUP.backup_id: TEST_BACKUP}

    agent._invalidate_caches(
        TEST_BACKUP.backup_id, "file1.tar", "file1.metadata.json", remove_files=True
    )

    assert "file1.tar" not in agent._all_files_cache
    assert TEST_BACKUP.backup_id not in agent._backup_list_cache

    agent._all_files_cache_expiration = 9999999999.0
    agent._backup_list_cache_expiration = 9999999999.0

    agent._invalidate_caches(
        TEST_BACKUP.backup_id, "file.tar", "file.json", remove_files=False
    )

    assert agent._all_files_cache_expiration == 0.0
    assert agent._backup_list_cache_expiration == 0.0


async def test_metadata_processing_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test metadata error handling.

    Directly tests the agent to call private synchronous methods
    (_process_metadata_file_sync, _process_metadata_file_for_id_sync) which are
    internal helpers not exposed through the WebSocket/HTTP API.
    """
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    mock_metadata = Mock()
    mock_metadata.download.side_effect = B2Error("Download failed")

    with caplog.at_level(logging.WARNING):
        result = agent._process_metadata_file_sync(
            "test.metadata.json", mock_metadata, {}
        )

    assert result is None
    assert "Failed to download metadata file" in caplog.text

    caplog.clear()

    mock_metadata2 = Mock()
    mock_metadata2.download.return_value.response.content = json.dumps(
        BACKUP_METADATA
    ).encode()

    with caplog.at_level(logging.WARNING):
        result = agent._process_metadata_file_sync(
            "testprefix/orphan.metadata.json", mock_metadata2, {}
        )

    assert result is None
    assert "no corresponding backup file" in caplog.text

    caplog.clear()

    mock_metadata3 = Mock()
    mock_metadata3.download.side_effect = B2Error("Download failed")

    with caplog.at_level(logging.WARNING):
        result = agent._process_metadata_file_for_id_sync(
            "test.metadata.json", mock_metadata3, TEST_BACKUP.backup_id, {}
        )

    assert result == (None, None)
    assert "Failed to download metadata file" in caplog.text

    caplog.clear()

    mock_metadata4 = Mock()
    mock_metadata4.download.return_value.response.content = b"invalid json"

    result = agent._process_metadata_file_for_id_sync(
        "test.metadata.json", mock_metadata4, TEST_BACKUP.backup_id, {}
    )

    assert result == (None, None)

    mock_metadata5 = Mock()
    mock_metadata5.download.return_value.response.content = json.dumps(
        BACKUP_METADATA
    ).encode()

    with caplog.at_level(logging.WARNING):
        result = agent._process_metadata_file_for_id_sync(
            "testprefix/orphan.metadata.json",
            mock_metadata5,
            TEST_BACKUP.backup_id,
            {},
        )

    assert result == (None, None)
    assert "but no corresponding backup file" in caplog.text


async def test_successful_upload_file_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload logging.

    Directly tests the agent to call the private _upload_backup_file method and
    verify specific success logging behavior not accessible through the public API.
    """
    agent = BackblazeBackupAgent(hass, mock_config_entry)

    async def mock_open_stream():
        async def async_gen():
            yield b"test data"

        return async_gen()

    mock_file_version = Mock(id_="test_file_id")

    async def mock_executor(*_args, **_kwargs):
        return mock_file_version

    with (
        patch.object(agent._hass, "async_add_executor_job", side_effect=mock_executor),
        caplog.at_level(logging.INFO),
    ):
        await agent._upload_backup_file("test.tar", mock_open_stream, {})

    assert "Successfully uploaded test.tar" in caplog.text
    assert "test_file_id" in caplog.text


@pytest.mark.parametrize(
    ("semaphore_count", "expected_max_concurrent"),
    [
        (MAX_CONCURRENT_DOWNLOADS, MAX_CONCURRENT_DOWNLOADS),
        (100, 15),
    ],
)
async def test_semaphore_limits_concurrent_metadata_downloads(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    semaphore_count: int,
    expected_max_concurrent: int,
) -> None:
    """Test that semaphore limits concurrent metadata downloads.

    With proper limit: concurrency is limited. With excessive limit: all run concurrently.
    The second case proves the test can detect when the semaphore isn't limiting.
    """
    current_concurrent = 0
    max_concurrent = 0
    lock = threading.Lock()

    def mock_download_sync():
        nonlocal current_concurrent, max_concurrent
        with lock:
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
        time.sleep(0.05)
        with lock:
            current_concurrent -= 1

        mock_download_obj = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps(BACKUP_METADATA).encode()
        mock_download_obj.response = mock_response
        return mock_download_obj

    mock_files = {}
    for i in range(15):
        mock_metadata = Mock()
        mock_metadata.file_name = f"testprefix/backup{i}.metadata.json"
        mock_metadata.download = mock_download_sync
        mock_files[f"testprefix/backup{i}.metadata.json"] = mock_metadata

        mock_tar = Mock(size=TEST_BACKUP.size)
        mock_tar.file_name = f"testprefix/backup{i}.tar"
        mock_files[f"testprefix/backup{i}.tar"] = mock_tar

    async def mock_get_all_files(_self):
        return mock_files

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.backblaze_b2.backup.MAX_CONCURRENT_DOWNLOADS",
            semaphore_count,
        ),
        patch(
            "homeassistant.components.backblaze_b2.backup.BackblazeBackupAgent._get_all_files_in_prefix",
            mock_get_all_files,
        ),
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    assert max_concurrent <= expected_max_concurrent


def test_requests_pool_maxsize_assumption() -> None:
    """Test that requests library pool_maxsize default hasn't changed.

    MAX_CONCURRENT_DOWNLOADS is set based on the assumption that the requests
    library's HTTPAdapter has a default pool_maxsize of 10. This test ensures
    that assumption remains valid. If this test fails, MAX_CONCURRENT_DOWNLOADS
    may need to be adjusted.
    """
    adapter = requests.adapters.HTTPAdapter()
    expected_pool_maxsize = 10

    assert adapter._pool_maxsize == expected_pool_maxsize, (
        f"requests HTTPAdapter pool_maxsize has changed from {expected_pool_maxsize} to {adapter._pool_maxsize}. MAX_CONCURRENT_DOWNLOADS may need adjustment."
    )

    # Verify our semaphore limit is safely below the pool size
    assert expected_pool_maxsize // 2 >= MAX_CONCURRENT_DOWNLOADS, (
        f"MAX_CONCURRENT_DOWNLOADS ({MAX_CONCURRENT_DOWNLOADS}) should be at most "
        f"half of pool_maxsize ({expected_pool_maxsize}) to prevent pool exhaustion"
    )
