"""Test the Google Drive backup platform."""

from dataclasses import replace
from io import StringIO
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import (
    ClientConnectionError,
    ClientPayloadError,
    ClientResponse,
    StreamReader,
)
from freezegun.api import FrozenDateTimeFactory
from google_drive_api.exceptions import GoogleDriveApiError
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_fixture_path
from pytest_homeassistant.test_util.aiohttp import mock_stream
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AddonInfo,
    AgentBackup,
)
from homeassistant.components.google_drive import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import CONFIG_ENTRY_TITLE, TEST_AGENT_ID

from tests.components.backup.common import (
    collect_upload_events,
    flush_upload_progress,
    upload_backup_via_http,
)

FOLDER_ID = "google-folder-id"
TEST_AGENT_BACKUP = AgentBackup(
    addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
    backup_id="test-backup",
    database_included=True,
    date="2025-01-01T01:23:45.678Z",
    extra_metadata={
        "with_automatic_settings": False,
    },
    folders=[],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Test",
    protected=False,
    size=987,
)
TEST_AGENT_BACKUP_RESULT = {
    "addons": [{"name": "Test", "slug": "test", "version": "1.0.0"}],
    "agents": {TEST_AGENT_ID: {"protected": False, "size": 987}},
    "backup_id": "test-backup",
    "database_included": True,
    "date": "2025-01-01T01:23:45.678Z",
    "extra_metadata": {"with_automatic_settings": False},
    "failed_addons": [],
    "failed_agent_ids": [],
    "failed_folders": [],
    "folders": [],
    "homeassistant_included": True,
    "homeassistant_version": "2024.12.0",
    "name": "Test",
    "with_automatic_settings": None,
}


# Protected with password "hunter2", padded beyond the 4 MiB read buffer so the
# backup is not read to the end when checking the password or decrypting it
PROTECTED_BACKUP_DATA = (
    get_fixture_path("test_backups/c0cb53bd.tar", BACKUP_DOMAIN).read_bytes()
    + b"\0" * 12 * 2**20
)


async def consume_stream(
    file_metadata: Any,
    open_stream: Any,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Consume the stream from the open_stream callable."""
    stream = await open_stream()
    async for _ in stream:
        pass


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Set up Google Drive integration."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api.list_files = AsyncMock(
        return_value={"files": [{"id": "HA folder ID", "name": "HA folder name"}]}
    )


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup agent info following config entry unload and setup."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [
            {"agent_id": "backup.local", "name": "local"},
            {"agent_id": TEST_AGENT_ID, "name": CONFIG_ENTRY_TITLE},
        ],
    }

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [{"agent_id": "backup.local", "name": "local"}]
    }

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [
            {"agent_id": "backup.local", "name": "local"},
            {"agent_id": TEST_AGENT_ID, "name": CONFIG_ENTRY_TITLE},
        ],
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent list backups."""
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]
        }
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [TEST_AGENT_BACKUP_RESULT]
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_list_backups_ignores_unreadable_metadata(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a backup whose description cannot be read is skipped.

    The description is editable from the Google Drive UI, so one unreadable
    file must not hide the others.
    """
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [
                {"id": "no description at all"},
                {"id": "not json", "description": "cleared by the user"},
                {"id": "not backup metadata", "description": '{"foo": "bar"}'},
                {"description": json.dumps(TEST_AGENT_BACKUP.as_dict())},
            ]
        }
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [TEST_AGENT_BACKUP_RESULT]
    assert "Ignoring backup file no description at all" in caplog.text
    assert "Ignoring backup file not json" in caplog.text
    assert "Ignoring backup file not backup metadata" in caplog.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # The backup manager calls extra_metadata.get() on every backup.
        ("extra_metadata", []),
        # The backup manager uses backup_id as a dict key.
        ("backup_id", ["not a string"]),
    ],
)
async def test_agents_list_backups_ignores_wrong_typed_metadata(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
    field: str,
    value: Any,
) -> None:
    """Test that metadata which decodes but has the wrong types is skipped.

    AgentBackup.from_dict does not enforce its annotations, so such a backup is
    only rejected once the backup manager uses it.
    """
    wrong_types = TEST_AGENT_BACKUP.as_dict()
    wrong_types[field] = value
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [
                {"id": "wrong types", "description": json.dumps(wrong_types)},
                {"description": json.dumps(TEST_AGENT_BACKUP.as_dict())},
            ]
        }
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [TEST_AGENT_BACKUP_RESULT]
    assert "Ignoring backup file wrong types" in caplog.text
    assert f"{field} is not a" in caplog.text


async def test_agents_list_backups_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
) -> None:
    """Test agent list backups fails."""
    mock_api.list_files = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == []
    assert response["result"]["agent_errors"] == {
        TEST_AGENT_ID: "Failed to list backups"
    }
    assert "Failed to list backups: some error" in caplog.text


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (TEST_AGENT_BACKUP.backup_id, TEST_AGENT_BACKUP_RESULT),
        ("12345", None),
    ],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    backup_id: str,
    expected_result: dict[str, Any] | None,
) -> None:
    """Test agent get backup."""
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]
        }
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == expected_result


async def test_agents_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent download backup."""
    mock_api.list_files = AsyncMock(
        side_effect=[
            {"files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]},
            {"files": [{"id": "backup-file-id"}]},
        ]
    )
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.content = mock_stream(b"backup data")
    mock_api.get_file_content = AsyncMock(return_value=mock_response)

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"

    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_download_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
) -> None:
    """Test agent download backup fails."""
    mock_api.list_files = AsyncMock(
        side_effect=[
            {"files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]},
            {"files": [{"id": "backup-file-id"}]},
        ]
    )
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.content = mock_stream(b"backup data")
    mock_api.get_file_content = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )
    assert resp.status == 500
    content = await resp.content.read()
    assert "Failed to download backup" in content.decode()
    assert "Failed to download backup: some error" in caplog.text


async def test_agents_download_file_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent download backup raises error if not found."""
    mock_api.list_files = AsyncMock(
        side_effect=[
            {"files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]},
            {"files": []},
        ]
    )

    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )
    assert resp.status == 404
    content = await resp.content.read()
    assert content == b""


async def test_agents_download_metadata_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent download backup raises error if not found."""
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [{"description": json.dumps(TEST_AGENT_BACKUP.as_dict())}]
        }
    )

    client = await hass_client()
    backup_id = "1234"
    assert backup_id != TEST_AGENT_BACKUP.backup_id

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={TEST_AGENT_ID}"
    )
    assert resp.status == 404
    assert await resp.content.read() == b""


async def test_agents_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent upload backup."""
    mock_api.resumable_upload_file = AsyncMock(side_effect=consume_stream)

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = TEST_AGENT_BACKUP
        resp = await client.post(
            f"/api/backup/upload?agent_id={TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup: {TEST_AGENT_BACKUP.backup_id}" in caplog.text
    assert f"Uploaded backup: {TEST_AGENT_BACKUP.backup_id}" in caplog.text

    mock_api.resumable_upload_file.assert_called_once()
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_upload_create_folder_if_missing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent upload backup creates folder if missing."""
    mock_api.list_files = AsyncMock(return_value={"files": []})
    mock_api.create_file = AsyncMock(
        return_value={"id": "new folder id", "name": "Home Assistant"}
    )
    mock_api.resumable_upload_file = AsyncMock(side_effect=consume_stream)

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = TEST_AGENT_BACKUP
        resp = await client.post(
            f"/api/backup/upload?agent_id={TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup: {TEST_AGENT_BACKUP.backup_id}" in caplog.text
    assert f"Uploaded backup: {TEST_AGENT_BACKUP.backup_id}" in caplog.text

    mock_api.create_file.assert_called_once()
    mock_api.resumable_upload_file.assert_called_once()
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


@pytest.mark.parametrize(
    ("upload_attempts", "chunks"),
    [
        pytest.param(1, [b"chunk1", b"chunk2"], id="single_attempt"),
        # A retried upload reopens and re-reads the backup file.
        pytest.param(
            2, [b"chunk1", b"chunk2", b"", b"chunk1", b"chunk2"], id="retried"
        ),
    ],
)
async def test_agents_upload_progress(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
    upload_attempts: int,
    chunks: list[bytes],
) -> None:
    """Test upload progress is reported per chunk and never goes backwards."""

    async def resumable_upload_file(
        file_metadata: Any, open_stream: Any, *args: Any, **kwargs: Any
    ) -> None:
        # A retried resumable upload reopens the stream from the beginning.
        for _ in range(upload_attempts):
            stream = await open_stream()
            async for _ in stream:
                # Report each chunk's progress in its own event
                flush_upload_progress(hass, freezer)

    mock_api.resumable_upload_file = AsyncMock(side_effect=resumable_upload_file)

    with collect_upload_events(hass, TEST_AGENT_ID) as events:
        resp = await upload_backup_via_http(
            await hass_client(), TEST_AGENT_ID, TEST_AGENT_BACKUP, chunks
        )

    assert resp.status == 201
    # The manager emits the first (0) and last (backup size) events
    assert [event.uploaded_bytes for event in events] == [
        0,
        6,
        12,
        TEST_AGENT_BACKUP.size,
    ]


async def test_agents_upload_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
) -> None:
    """Test agent upload backup fails."""
    mock_api.resumable_upload_file = AsyncMock(
        side_effect=GoogleDriveApiError("some error")
    )
    mock_api.list_files = AsyncMock(
        side_effect=[
            {"files": [{"id": "HA folder ID", "name": "HA folder name"}]},
            {"files": []},
            {"files": [{"id": "HA folder ID", "name": "HA folder name"}]},
        ]
    )

    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = TEST_AGENT_BACKUP
        resp = await client.post(
            f"/api/backup/upload?agent_id={TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )
        await hass.async_block_till_done()

    assert resp.status == 201
    assert "Failed to upload backup: some error" in caplog.text


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test agent delete backup."""
    mock_api.list_files = AsyncMock(return_value={"files": [{"id": "backup-file-id"}]})
    mock_api.delete_file = AsyncMock(return_value=None)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_error_translations": {}, "agent_errors": {}}

    mock_api.delete_file.assert_called_once()
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot


async def test_agents_delete_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
) -> None:
    """Test agent delete backup fails."""
    mock_api.list_files = AsyncMock(return_value={"files": [{"id": "backup-file-id"}]})
    mock_api.delete_file = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_error_translations": {
            TEST_AGENT_ID: {
                "translation_domain": "google_drive",
                "translation_key": "delete_failed",
                "translation_placeholders": None,
            }
        },
        "agent_errors": {TEST_AGENT_ID: "Failed to delete backup"},
    }
    assert "Failed to delete backup: some error" in caplog.text


async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_api: MagicMock,
) -> None:
    """Test agent delete backup not found."""
    mock_api.list_files = AsyncMock(return_value={"files": []})

    client = await hass_ws_client(hass)
    backup_id = "1234"

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_error_translations": {}, "agent_errors": {}}

    mock_api.delete_file.assert_not_called()


@pytest.fixture
def backup_data() -> bytes:
    """Backup data, override in tests to change defaults."""
    return b"backup data"


@pytest.fixture
def backup_protected() -> bool:
    """Backup protected, override in tests to change defaults."""
    return False


@pytest.fixture
def downloaded_responses(
    mock_api: MagicMock, backup_data: bytes, backup_protected: bool
) -> list[AsyncMock]:
    """Mock the backup and return the responses of downloaded backup archives."""
    backup = replace(TEST_AGENT_BACKUP, protected=backup_protected)
    mock_api.list_files = AsyncMock(
        return_value={
            "files": [
                {"id": "backup-file-id", "description": json.dumps(backup.as_dict())}
            ]
        }
    )
    responses: list[AsyncMock] = []

    def get_file_content(*args: Any, **kwargs: Any) -> AsyncMock:
        response = AsyncMock(spec=ClientResponse)
        response.content = mock_stream(backup_data)
        responses.append(response)
        return response

    mock_api.get_file_content = AsyncMock(side_effect=get_file_content)
    return responses


@pytest.mark.parametrize(
    ("backup_protected", "backup_data"),
    [pytest.param(True, PROTECTED_BACKUP_DATA, id="protected_backup")],
)
@pytest.mark.parametrize(
    ("password", "success"),
    [
        pytest.param("hunter2", True, id="correct_password"),
        pytest.param("wrong", False, id="wrong_password"),
    ],
)
async def test_can_decrypt_on_download_closes_response(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    downloaded_responses: list[AsyncMock],
    password: str,
    success: bool,
) -> None:
    """Test the download is closed after checking the password of a backup."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/can_decrypt_on_download",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
            "agent_id": TEST_AGENT_ID,
            "password": password,
        }
    )
    assert (await client.receive_json())["success"] is success

    assert len(downloaded_responses) == 1
    downloaded_responses[0].close.assert_called_once()


@pytest.mark.parametrize(
    ("backup_protected", "backup_data"),
    [pytest.param(True, PROTECTED_BACKUP_DATA, id="protected_backup")],
)
@pytest.mark.parametrize(
    "query",
    [
        pytest.param("", id="no_password"),
        pytest.param("&password=hunter2", id="correct_password"),
        pytest.param("&password=wrong", id="wrong_password"),
    ],
)
async def test_agents_download_closes_response(
    hass_client: ClientSessionGenerator,
    downloaded_responses: list[AsyncMock],
    query: str,
) -> None:
    """Test the download is closed when the backup is downloaded."""
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}{query}"
    )
    assert resp.status == 200
    await resp.read()

    assert len(downloaded_responses) == 1
    downloaded_responses[0].close.assert_called_once()


async def test_agents_download_closes_response_on_read_error(
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
    downloaded_responses: list[AsyncMock],
) -> None:
    """Test the download is closed when reading the backup fails."""
    get_file_content = mock_api.get_file_content.side_effect

    def get_failing_file_content(*args: Any, **kwargs: Any) -> AsyncMock:
        response = get_file_content(*args, **kwargs)
        response.content = StreamReader(Mock(_reading_paused=False), limit=2**16)
        response.content.set_exception(ClientConnectionError())
        return response

    mock_api.get_file_content.side_effect = get_failing_file_content
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )
    with pytest.raises(ClientPayloadError):
        await resp.read()

    assert len(downloaded_responses) == 1
    downloaded_responses[0].close.assert_called_once()


async def test_agents_download_empty_chunk_before_eof(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: MagicMock,
    downloaded_responses: list[AsyncMock],
) -> None:
    """Test an empty chunk at an HTTP chunk boundary does not end the download."""
    get_file_content = mock_api.get_file_content.side_effect

    def get_chunked_file_content(*args: Any, **kwargs: Any) -> AsyncMock:
        response = get_file_content(*args, **kwargs)
        response.content = StreamReader(
            Mock(_reading_paused=False), 2**16, loop=hass.loop
        )
        for data in (b"backup", b"", b" data"):
            response.content.begin_http_chunk_receiving()
            response.content.feed_data(data)
            response.content.end_http_chunk_receiving()
        response.content.feed_eof()
        return response

    mock_api.get_file_content.side_effect = get_chunked_file_content
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={TEST_AGENT_ID}"
    )
    assert resp.status == 200
    assert await resp.read() == b"backup data"

    assert len(downloaded_responses) == 1
    downloaded_responses[0].close.assert_called_once()
