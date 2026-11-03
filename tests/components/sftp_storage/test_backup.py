"""Test the Backup SFTP Location platform."""

import asyncio
from io import BytesIO, StringIO
import json
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ClientPayloadError
from asyncssh.sftp import SFTPError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import get_fixture_path
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, async_get_manager
from homeassistant.components.sftp_storage import client as sftp_client
from homeassistant.components.sftp_storage.backup import (
    async_register_backup_agents_listener,
)
from homeassistant.components.sftp_storage.const import (
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .asyncssh_mock import SFTPOpenMock, SSHClientConnectionMock, async_context_manager
from .conftest import (
    BACKUP_METADATA,
    CONFIG_ENTRY_TITLE,
    TEST_AGENT_BACKUP,
    TEST_AGENT_ID,
    ComponentSetup,
)

from tests.components.backup.common import (
    collect_upload_events,
    flush_upload_progress,
    upload_backup_via_http,
)

# Protected with password "hunter2", padded beyond the 4 MiB read buffer so the
# backup is not read to the end when checking the password or decrypting it
PROTECTED_BACKUP_DATA = (
    get_fixture_path("test_backups/c0cb53bd.tar", BACKUP_DOMAIN).read_bytes()
    + b"\0" * 12 * 2**20
)


@pytest.fixture(autouse=True)
async def mock_setup_integration(
    setup_integration: ComponentSetup,
) -> None:
    """Set up the integration automatically for backup tests."""
    await setup_integration()


def generate_result(metadata: dict) -> dict:
    """Generates an expected result from metadata."""

    expected_result: dict = metadata["metadata"].copy()
    expected_result["agents"] = {
        f"{DOMAIN}.{TEST_AGENT_ID}": {
            "protected": expected_result.pop("protected"),
            "size": expected_result.pop("size"),
        }
    }
    expected_result.update(
        {
            "failed_addons": [],
            "failed_agent_ids": [],
            "failed_folders": [],
            "with_automatic_settings": None,
        }
    )
    return expected_result


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup agent info following config entry unload and setup."""
    client = await hass_ws_client(hass)
    local_agent = {"agent_id": "backup.local", "name": "local"}
    sftp_agent = {"agent_id": f"{DOMAIN}.{TEST_AGENT_ID}", "name": CONFIG_ENTRY_TITLE}

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agents": [local_agent, sftp_agent]}

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agents": [local_agent]}

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agents": [local_agent, sftp_agent]}


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent list backups."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)
    expected_result = generate_result(BACKUP_METADATA)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [expected_result]


async def test_agents_list_backups_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent list backups fails."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)
    mock_ssh_connection._sftp._mock_open._mock_read.side_effect = SFTPError(
        2, "Error message"
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backups"] == []
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{TEST_AGENT_ID}": (
            "Remote server error while attempting to list backups: Error message"
        )
    }


async def test_agents_list_backups_include_bad_metadata(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test agent list backups."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA, with_bad=True)
    expected_result = generate_result(BACKUP_METADATA)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [expected_result]
    # Called two times, one for bad backup metadata and once for good
    assert mock_ssh_connection._sftp._mock_open._mock_read.call_count == 2
    assert (
        "Failed to load backup metadata from file:"
        " /backup_location/invalid.metadata.json."
        " Expecting value: line 1 column 1 (char 0)" in caplog.messages
    )


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (TEST_AGENT_BACKUP.backup_id, generate_result(BACKUP_METADATA)),
        ("12345", None),
    ],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    backup_id: str,
    expected_result: dict[str, Any] | None,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent get backup."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["backup"] == expected_result


async def test_agents_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent download backup."""
    client = await hass_client()
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)

    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
    mock_ssh_connection._sftp._mock_open.close.assert_awaited()


async def test_agents_download_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent download backup fails."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)

    # This will cause `FileNotFoundError` exception in
    # `BackupAgentClient.iter_file() method.`
    mock_ssh_connection._sftp._mock_exists.side_effect = [True, False]
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 404

    # This will raise `RuntimeError` causing Internal Server Error,
    # mimicking that the SFTP setup failed.
    mock_ssh_connection._sftp = None
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 500
    content = await resp.content.read()
    assert b"Internal Server Error" in content


async def test_agents_download_metadata_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent download backup raises error if not found."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)

    mock_ssh_connection._sftp._mock_exists.return_value = False
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 404
    content = await resp.content.read()
    assert content.decode() == ""


async def test_agents_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent upload backup."""
    client = await hass_client()

    with (
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
    ):
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert f"Uploading backup: {TEST_AGENT_BACKUP.backup_id}" in caplog.text
    assert (
        f"Successfully uploaded backup id: {TEST_AGENT_BACKUP.backup_id}" in caplog.text
    )
    # Called write 2 times
    # 1. When writing backup file
    # 2. When writing metadata file
    assert mock_ssh_connection._sftp._mock_open._mock_write.call_count == 2

    # This is 'backup file'
    assert (
        b"test"
        in mock_ssh_connection._sftp._mock_open._mock_write.call_args_list[0].args
    )

    # This is backup metadata
    uploaded_metadata = json.loads(
        mock_ssh_connection._sftp._mock_open._mock_write.call_args_list[1].args[0]
    )["metadata"]
    assert uploaded_metadata == BACKUP_METADATA["metadata"]


async def test_agents_upload_progress(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that upload progress is reported after each written chunk."""
    agent_id = f"{DOMAIN}.{TEST_AGENT_ID}"
    mock_write = mock_ssh_connection._sftp._mock_open._mock_write
    # Report each chunk's progress in its own event
    mock_write.side_effect = lambda *args: flush_upload_progress(hass, freezer)

    with collect_upload_events(hass, agent_id) as events:
        resp = await upload_backup_via_http(
            await hass_client(), agent_id, TEST_AGENT_BACKUP, [b"abc", b"defgh"]
        )

    assert resp.status == 201
    assert [c.args[0] for c in mock_write.call_args_list[:2]] == [b"abc", b"defgh"]
    # The manager emits the first (0) and last (backup size) events
    assert [e.uploaded_bytes for e in events] == [0, 3, 8, TEST_AGENT_BACKUP.size]


async def test_agents_upload_fail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent upload backup fails."""
    client = await hass_client()
    mock_ssh_connection._sftp._mock_open._mock_write.side_effect = SFTPError(
        2, "Error message"
    )

    with (
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_AGENT_BACKUP,
        ),
    ):
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{TEST_AGENT_ID}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert (
        f"Unexpected error for {DOMAIN}.{TEST_AGENT_ID}: Error message"
        in caplog.messages
    )


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent delete backup."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)

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

    # Called 2 times, to remove metadata and backup file.
    assert mock_ssh_connection._sftp._mock_unlink.call_count == 2


@pytest.mark.parametrize(
    ("exists_side_effect", "expected_result"),
    [
        (
            [True, False],
            {"agent_error_translations": {}, "agent_errors": {}},
        ),  # First `True` is to confirm the metadata file exists
        (
            SFTPError(0, "manual"),
            {
                "agent_error_translations": {},
                "agent_errors": {
                    f"{DOMAIN}.{TEST_AGENT_ID}": (
                        f"Failed to delete backup id:"
                        f" {TEST_AGENT_BACKUP.backup_id}: manual"
                    )
                },
            },
        ),
    ],
    ids=["file_not_found_exc", "sftp_error_exc"],
)
async def test_agents_delete_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
    exists_side_effect: bool | Exception,
    expected_result: dict[str, dict[str, str]],
) -> None:
    """Test agent delete backup fails."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)
    mock_ssh_connection._sftp._mock_exists.side_effect = exists_side_effect

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == expected_result


async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test agent delete backup not found."""
    mock_ssh_connection.mock_setup_backup(BACKUP_METADATA)

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


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [
        listener
    ]  # make sure it's the last listener
    remove_listener()

    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data


@pytest.fixture
def ssh_connections(
    mock_ssh_connection: SSHClientConnectionMock,
) -> list[SSHClientConnectionMock]:
    """Return the SSH connections opened after the integration was set up.

    A download opens three: to get the backup, to find the archive and to read it.
    """
    connections: list[SSHClientConnectionMock] = []

    @async_context_manager
    async def mock_connect(*args: Any, **kwargs: Any) -> SSHClientConnectionMock:
        connection = SSHClientConnectionMock()
        connection._sftp = mock_ssh_connection._sftp
        connection.close = Mock()
        connections.append(connection)
        return connection

    sftp_client.connect.side_effect = mock_connect
    return connections


@pytest.fixture
def backup_data() -> bytes:
    """Backup data, override in tests to change defaults."""
    return b"backup data"


@pytest.fixture
def downloaded_files(
    mock_ssh_connection: SSHClientConnectionMock, backup_data: bytes
) -> list[SFTPOpenMock]:
    """Mock the backup and return the downloaded backup archive files."""
    sftp = mock_ssh_connection._sftp
    sftp._mock_listdir.return_value = [f"{TEST_AGENT_BACKUP.backup_id}.metadata.json"]
    sftp._mock_open._mock_read.return_value = json.dumps(BACKUP_METADATA)
    files: list[SFTPOpenMock] = []

    @async_context_manager
    async def mock_open(path: str, *args: Any, **kwargs: Any) -> SFTPOpenMock:
        if path != BACKUP_METADATA["file_path"]:
            return sftp._mock_open
        file = SFTPOpenMock()
        file._mock_read.side_effect = BytesIO(backup_data).read
        files.append(file)
        return file

    sftp.open = mock_open
    return files


@pytest.mark.parametrize(
    "backup_data", [pytest.param(PROTECTED_BACKUP_DATA, id="protected_backup")]
)
@pytest.mark.parametrize(
    ("password", "success"),
    [
        pytest.param("hunter2", True, id="correct_password"),
        pytest.param("wrong", False, id="wrong_password"),
    ],
)
async def test_can_decrypt_on_download_closes_connection(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    ssh_connections: list[SSHClientConnectionMock],
    downloaded_files: list[SFTPOpenMock],
    password: str,
    success: bool,
) -> None:
    """Test the download is closed after checking the password of a backup."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/can_decrypt_on_download",
            "backup_id": TEST_AGENT_BACKUP.backup_id,
            "agent_id": f"{DOMAIN}.{TEST_AGENT_ID}",
            "password": password,
        }
    )
    assert (await client.receive_json())["success"] is success

    assert len(downloaded_files) == 1
    downloaded_files[0].close.assert_awaited_once()
    assert [conn.close.call_count for conn in ssh_connections] == [1, 1, 1]


@pytest.mark.parametrize(
    "backup_data", [pytest.param(PROTECTED_BACKUP_DATA, id="protected_backup")]
)
@pytest.mark.parametrize(
    "query",
    [
        pytest.param("", id="no_password"),
        pytest.param("&password=hunter2", id="correct_password"),
        pytest.param("&password=wrong", id="wrong_password"),
    ],
)
async def test_agents_download_closes_connection(
    hass_client: ClientSessionGenerator,
    ssh_connections: list[SSHClientConnectionMock],
    downloaded_files: list[SFTPOpenMock],
    query: str,
) -> None:
    """Test the download is closed when the backup is downloaded."""
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}{query}"
    )
    assert resp.status == 200
    await resp.read()

    assert len(downloaded_files) == 1
    downloaded_files[0].close.assert_awaited_once()
    assert [conn.close.call_count for conn in ssh_connections] == [1, 1, 1]


async def test_agents_download_closes_connection_on_read_error(
    hass_client: ClientSessionGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
    ssh_connections: list[SSHClientConnectionMock],
    downloaded_files: list[SFTPOpenMock],
) -> None:
    """Test the download is closed when reading the backup fails."""
    open_file = mock_ssh_connection._sftp.open

    @async_context_manager
    async def mock_open(path: str, *args: Any, **kwargs: Any) -> SFTPOpenMock:
        file = await open_file(path, *args, **kwargs)
        if path == BACKUP_METADATA["file_path"]:
            file._mock_read.side_effect = SFTPError(0, "read failed")
        return file

    mock_ssh_connection._sftp.open = mock_open
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    with pytest.raises(ClientPayloadError):
        await resp.read()

    assert len(downloaded_files) == 1
    assert [conn.close.call_count for conn in ssh_connections] == [1, 1, 1]


async def test_agents_download_closes_connection_on_open_error(
    hass_client: ClientSessionGenerator,
    mock_ssh_connection: SSHClientConnectionMock,
    ssh_connections: list[SSHClientConnectionMock],
    downloaded_files: list[SFTPOpenMock],
) -> None:
    """Test the download is closed when opening the backup fails."""
    open_file = mock_ssh_connection._sftp.open

    @async_context_manager
    async def mock_open(path: str, *args: Any, **kwargs: Any) -> SFTPOpenMock:
        if path == BACKUP_METADATA["file_path"]:
            raise SFTPError(0, "no file")
        return await open_file(path, *args, **kwargs)

    mock_ssh_connection._sftp.open = mock_open
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    with pytest.raises(ClientPayloadError):
        await resp.read()

    assert not downloaded_files
    assert [conn.close.call_count for conn in ssh_connections] == [1, 1, 1]


async def test_agents_download_closed_while_connecting(
    hass: HomeAssistant,
    mock_ssh_connection: SSHClientConnectionMock,
    ssh_connections: list[SSHClientConnectionMock],
    downloaded_files: list[SFTPOpenMock],
) -> None:
    """Test the connection is closed if the download is closed while connecting.

    The backup integration doesn't close a download from another task while it is
    read, so the download stream is used directly.
    """
    agent = async_get_manager(hass).backup_agents[f"{DOMAIN}.{TEST_AGENT_ID}"]
    stream = await agent.async_download_backup(TEST_AGENT_BACKUP.backup_id)

    connect = sftp_client.connect.side_effect
    connecting = asyncio.Event()
    connected = asyncio.Event()

    @async_context_manager
    async def paused_connect(*args: Any, **kwargs: Any) -> SSHClientConnectionMock:
        connecting.set()
        await connected.wait()
        return await connect(*args, **kwargs)

    sftp_client.connect.side_effect = paused_connect
    open_file = mock_ssh_connection._sftp.open

    @async_context_manager
    async def mock_open(path: str, *args: Any, **kwargs: Any) -> SFTPOpenMock:
        if path == BACKUP_METADATA["file_path"]:
            raise SFTPError(0, "no file")
        return await open_file(path, *args, **kwargs)

    mock_ssh_connection._sftp.open = mock_open

    read = asyncio.create_task(anext(stream))
    await connecting.wait()
    stream.close()
    connected.set()
    with pytest.raises(SFTPError, match="no file"):
        await read

    assert not downloaded_files
    # One connection to find the archive, one to read it
    assert [conn.close.call_count for conn in ssh_connections] == [1, 1]
