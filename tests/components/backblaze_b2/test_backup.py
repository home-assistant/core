"""Backblaze B2 backup agent tests."""

from collections.abc import AsyncGenerator
from io import StringIO
import json
import logging
import threading
import time
from unittest.mock import Mock, patch

from b2sdk._internal.raw_simulator import BucketSimulator
from b2sdk.v2.exception import B2Error
import pytest

from homeassistant.components.backblaze_b2.backup import (
    _parse_metadata,
    async_register_backup_agents_listener,
)
from homeassistant.components.backblaze_b2.const import (
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN
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


@pytest.fixture
def mock_backup_files():
    """Create standard mock backup file and metadata file."""
    mock_main = Mock()
    mock_main.file_name = f"testprefix/{TEST_BACKUP.backup_id}.tar"
    mock_main.size = TEST_BACKUP.size
    mock_main.delete = Mock()

    mock_metadata = Mock()
    mock_metadata.file_name = f"testprefix/{TEST_BACKUP.backup_id}.metadata.json"
    mock_metadata.size = 100

    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps(BACKUP_METADATA).encode()
    mock_download.response = mock_response
    mock_metadata.download = Mock(return_value=mock_download)
    mock_metadata.delete = Mock()

    return mock_main, mock_metadata


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
    mock_backup_files,
) -> None:
    """Test deleting backup."""
    client = await hass_ws_client(hass)
    mock_main, mock_metadata = mock_backup_files

    def mock_ls(_self, _prefix=""):
        return iter([(mock_main, None), (mock_metadata, None)])

    with patch.object(BucketSimulator, "ls", mock_ls):
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    mock_main.delete.assert_called_once()
    mock_metadata.delete.assert_called_once()


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
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test exception handling for nonexistent backup."""
    client = await hass_client()

    def mock_ls_empty(_self, _prefix=""):
        return iter([])

    with patch.object(BucketSimulator, "ls", mock_ls_empty):
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
    mock_backup_files,
    error_type: str,
    exception: type[Exception],
) -> None:
    """Test error handling during deletion."""
    client = await hass_ws_client(hass)
    mock_main, mock_metadata = mock_backup_files
    mock_metadata.delete = Mock(side_effect=exception("Delete failed"))

    def mock_ls(_self, _prefix=""):
        return iter([(mock_main, None), (mock_metadata, None)])

    with patch.object(BucketSimulator, "ls", mock_ls):
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
    """Test error handling during list."""
    client = await hass_ws_client(hass)

    def mock_ls_error(_self, _prefix=""):
        raise B2Error("API error")

    with patch.object(BucketSimulator, "ls", mock_ls_error):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    assert (
        f"{DOMAIN}.{mock_config_entry.entry_id}" in response["result"]["agent_errors"]
    )


async def test_error_during_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling during get."""
    client = await hass_ws_client(hass)

    def mock_ls_error(_self, _prefix=""):
        raise B2Error("API error")

    with patch.object(BucketSimulator, "ls", mock_ls_error):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": "test_backup"}
        )
        response = await client.receive_json()

    assert response["success"]
    assert (
        f"{DOMAIN}.{mock_config_entry.entry_id}" in response["result"]["agent_errors"]
    )


async def test_metadata_file_download_error_during_list(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test metadata download error handling."""
    client = await hass_ws_client(hass)

    mock_metadata = Mock()
    mock_metadata.file_name = "testprefix/test.metadata.json"
    mock_metadata.download = Mock(side_effect=B2Error("Download failed"))

    mock_tar = Mock()
    mock_tar.file_name = "testprefix/test.tar"

    def mock_ls(_self, _prefix=""):
        return iter([(mock_metadata, None), (mock_tar, None)])

    with patch.object(BucketSimulator, "ls", mock_ls):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]


async def test_delete_with_metadata_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_backup_files,
) -> None:
    """Test error handling during metadata deletion."""
    client = await hass_ws_client(hass)
    mock_main, mock_metadata = mock_backup_files
    mock_metadata.delete = Mock(side_effect=B2Error("Delete failed"))

    def mock_ls(_self, _prefix=""):
        return iter([(mock_main, None), (mock_metadata, None)])

    with patch.object(BucketSimulator, "ls", mock_ls):
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()

    assert response["success"]
    assert (
        f"{DOMAIN}.{mock_config_entry.entry_id}" in response["result"]["agent_errors"]
    )
    mock_main.delete.assert_called_once()
    mock_metadata.delete.assert_called_once()


async def test_download_backup_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test downloading nonexistent backup."""
    client = await hass_ws_client(hass)

    def mock_ls_empty(_self, _prefix=""):
        return iter([])

    with patch.object(BucketSimulator, "ls", mock_ls_empty):
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

    mock_metadata = Mock()
    mock_metadata.file_name = "testprefix/bad.metadata.json"
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = b"not valid json"
    mock_download.response = mock_response
    mock_metadata.download = Mock(return_value=mock_download)

    mock_tar = Mock()
    mock_tar.file_name = "testprefix/bad.tar"

    def mock_ls(_self, _prefix=""):
        return iter([(mock_metadata, None), (mock_tar, None)])

    with (
        patch.object(BucketSimulator, "ls", mock_ls),
        caplog.at_level(logging.WARNING),
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]


async def test_upload_with_cleanup_and_logging(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload logging and cleanup."""
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
        caplog.at_level(logging.DEBUG),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert any("Main backup file upload finished" in msg for msg in caplog.messages)
    assert any("Metadata file upload finished" in msg for msg in caplog.messages)
    assert any("Backup upload complete" in msg for msg in caplog.messages)

    caplog.clear()

    mock_file_info = Mock()
    mock_file_info.delete = Mock()

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
        patch.object(
            BucketSimulator,
            "upload_bytes",
            side_effect=B2Error("Metadata upload failed"),
        ),
        patch.object(
            BucketSimulator, "get_file_info_by_name", return_value=mock_file_info
        ),
        caplog.at_level(logging.DEBUG),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    mock_file_info.delete.assert_called_once()
    assert any(
        "Successfully deleted partially uploaded" in msg for msg in caplog.messages
    )


async def test_upload_with_cleanup_failure(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload with cleanup failure when metadata upload fails."""
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
        patch.object(
            BucketSimulator,
            "upload_bytes",
            side_effect=B2Error("Metadata upload failed"),
        ),
        patch.object(
            BucketSimulator,
            "get_file_info_by_name",
            side_effect=B2Error("Cleanup failed"),
        ),
        caplog.at_level(logging.DEBUG),
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert any(
        "Failed to clean up partially uploaded main backup file" in msg
        for msg in caplog.messages
    )


async def test_cache_behavior(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup list caching."""
    client = await hass_ws_client(hass)

    call_count = []
    original_ls = BucketSimulator.ls

    def ls_with_counter(self, prefix=""):
        call_count.append(1)
        return original_ls(self, prefix)

    with patch.object(BucketSimulator, "ls", ls_with_counter):
        await client.send_json_auto_id({"type": "backup/info"})
        response1 = await client.receive_json()
        assert response1["success"]
        first_call_count = len(call_count)
        assert first_call_count > 0

        await client.send_json_auto_id({"type": "backup/info"})
        response2 = await client.receive_json()
        assert response2["success"]
        assert len(call_count) == first_call_count

        assert response1["result"]["backups"] == response2["result"]["backups"]


async def test_metadata_processing_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test metadata error handling."""
    client = await hass_ws_client(hass)

    mock_metadata = Mock()
    mock_metadata.file_name = "testprefix/test.metadata.json"
    mock_metadata.download = Mock(side_effect=B2Error("Download failed"))

    mock_tar = Mock()
    mock_tar.file_name = "testprefix/test.tar"

    def mock_ls_download_error(_self, _prefix=""):
        return iter([(mock_metadata, None), (mock_tar, None)])

    with (
        patch.object(BucketSimulator, "ls", mock_ls_download_error),
        caplog.at_level(logging.WARNING),
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    assert "backups" in response["result"]

    caplog.clear()

    mock_metadata3 = Mock()
    mock_metadata3.file_name = f"testprefix/{TEST_BACKUP.backup_id}.metadata.json"
    mock_metadata3.download = Mock(side_effect=B2Error("Download failed"))

    mock_tar3 = Mock()
    mock_tar3.file_name = f"testprefix/{TEST_BACKUP.backup_id}.tar"

    def mock_ls_id_error(_self, _prefix=""):
        return iter([(mock_metadata3, None), (mock_tar3, None)])

    with patch.object(BucketSimulator, "ls", mock_ls_id_error):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] is None

    caplog.clear()

    mock_metadata4 = Mock()
    mock_metadata4.file_name = f"testprefix/{TEST_BACKUP.backup_id}.metadata.json"
    mock_download4 = Mock()
    mock_response4 = Mock()
    mock_response4.content = b"invalid json"
    mock_download4.response = mock_response4
    mock_metadata4.download = Mock(return_value=mock_download4)

    mock_tar4 = Mock()
    mock_tar4.file_name = f"testprefix/{TEST_BACKUP.backup_id}.tar"

    def mock_ls_invalid_json(_self, _prefix=""):
        return iter([(mock_metadata4, None), (mock_tar4, None)])

    with patch.object(BucketSimulator, "ls", mock_ls_invalid_json):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] is None


async def test_download_triggers_backup_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_backup_files,
) -> None:
    """Test race condition where backup disappears during download."""
    client = await hass_client()
    mock_main, mock_metadata = mock_backup_files
    ls_call_count = [0]

    def mock_ls_race_condition(_self, _prefix=""):
        ls_call_count[0] += 1
        if ls_call_count[0] == 1:
            return iter([(mock_main, None), (mock_metadata, None)])
        return iter([])

    with (
        patch.object(BucketSimulator, "ls", mock_ls_race_condition),
        patch("homeassistant.components.backblaze_b2.backup.CACHE_TTL", 0),
    ):
        resp = await client.get(
            f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
        )
        assert resp.status == 404


async def test_get_backup_cache_paths(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test cache hit and update paths."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/info"})
    response1 = await client.receive_json()
    assert response1["success"]
    assert len(response1["result"]["backups"]) > 0

    await client.send_json_auto_id(
        {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
    )
    response2 = await client.receive_json()
    assert response2["success"]
    assert response2["result"]["backup"]["backup_id"] == TEST_BACKUP.backup_id

    await client.send_json_auto_id(
        {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
    )
    response3 = await client.receive_json()
    assert response3["success"]
    assert response3["result"]["backup"]["backup_id"] == TEST_BACKUP.backup_id


async def test_metadata_json_parse_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test ValueError handling when metadata JSON parsing fails."""
    client = await hass_ws_client(hass)

    mock_metadata = Mock()
    mock_metadata.file_name = f"testprefix/{TEST_BACKUP.backup_id}.metadata.json"
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = b"{ invalid json }"
    mock_download.response = mock_response
    mock_metadata.download = Mock(return_value=mock_download)

    mock_tar = Mock()
    mock_tar.file_name = f"testprefix/{TEST_BACKUP.backup_id}.tar"

    def mock_ls(_self, _prefix=""):
        return iter([(mock_metadata, None), (mock_tar, None)])

    with patch.object(BucketSimulator, "ls", mock_ls):
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] is None


async def test_orphaned_metadata_files(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of metadata files without corresponding tar files."""
    client = await hass_ws_client(hass)

    mock_metadata = Mock()
    mock_metadata.file_name = f"testprefix/{TEST_BACKUP.backup_id}.metadata.json"
    mock_download = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps(BACKUP_METADATA).encode()
    mock_download.response = mock_response
    mock_metadata.download = Mock(return_value=mock_download)

    def mock_ls(_self, _prefix=""):
        return iter([(mock_metadata, None)])

    with (
        patch.object(BucketSimulator, "ls", mock_ls),
        caplog.at_level(logging.WARNING),
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        response1 = await client.receive_json()
        assert response1["success"]

        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
        )
        response2 = await client.receive_json()
        assert response2["success"]
        assert response2["result"]["backup"] is None

    assert any(
        "no corresponding backup file" in record.message for record in caplog.records
    )


async def test_get_backup_updates_cache(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_backup_files,
) -> None:
    """Test cache update when metadata initially fails then succeeds."""
    client = await hass_ws_client(hass)
    mock_main, mock_metadata = mock_backup_files
    download_call_count = [0]

    def mock_download():
        download_call_count[0] += 1
        mock_download_obj = Mock()
        mock_response = Mock()
        if download_call_count[0] == 1:
            mock_response.content = b"{ invalid json }"
        else:
            mock_response.content = json.dumps(BACKUP_METADATA).encode()
        mock_download_obj.response = mock_response
        return mock_download_obj

    mock_metadata.download = mock_download

    def mock_ls(_self, _prefix=""):
        return iter([(mock_main, None), (mock_metadata, None)])

    with patch.object(BucketSimulator, "ls", mock_ls):
        await client.send_json_auto_id({"type": "backup/info"})
        response1 = await client.receive_json()
        assert response1["success"]
        assert len(response1["result"]["backups"]) == 0

        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id}
        )
        response2 = await client.receive_json()
        assert response2["success"]
        assert response2["result"]["backup"]["backup_id"] == TEST_BACKUP.backup_id


async def test_delete_clears_backup_cache(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_backup_files,
) -> None:
    """Test that deleting a backup clears it from cache."""
    client = await hass_ws_client(hass)
    mock_main, mock_metadata = mock_backup_files

    def mock_ls(_self, _prefix=""):
        return iter([(mock_main, None), (mock_metadata, None)])

    with patch.object(BucketSimulator, "ls", mock_ls):
        await client.send_json_auto_id({"type": "backup/info"})
        response1 = await client.receive_json()
        assert response1["success"]
        assert len(response1["result"]["backups"]) > 0

        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id}
        )
        response2 = await client.receive_json()

    assert response2["success"]
    mock_main.delete.assert_called_once()
    mock_metadata.delete.assert_called_once()


async def test_metadata_downloads_are_sequential(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that metadata downloads are processed sequentially to avoid exhausting executor pool."""
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

    mock_files = []
    for i in range(15):
        mock_metadata = Mock()
        mock_metadata.file_name = f"testprefix/backup{i}.metadata.json"
        mock_metadata.download = mock_download_sync

        mock_tar = Mock()
        mock_tar.file_name = f"testprefix/backup{i}.tar"
        mock_tar.size = TEST_BACKUP.size

        mock_files.extend([(mock_metadata, None), (mock_tar, None)])

    def mock_ls(_self, _prefix=""):
        return iter(mock_files)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(BucketSimulator, "ls", mock_ls):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    # Verify downloads were sequential (max 1 at a time)
    assert max_concurrent == 1
