"""Test the Backup SFTP Location platform."""

from io import StringIO
import json
from typing import Any
from unittest.mock import MagicMock, patch

from asyncssh.sftp import SFTPError
import pytest

from homeassistant.components.sftp_storage.backup import (
    async_register_backup_agents_listener,
)
from homeassistant.components.sftp_storage.const import (
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .asyncssh_mock import SSHClientConnectionMock
from .conftest import (
    BACKUP_METADATA,
    CONFIG_ENTRY_TITLE,
    TEST_AGENT_BACKUP,
    TEST_AGENT_ID,
    ComponentSetup,
)

from tests.typing import ClientSessionGenerator, WebSocketGenerator


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
    """Test backup agent info."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [
            {"agent_id": "backup.local", "name": "local"},
            {"agent_id": f"{DOMAIN}.{TEST_AGENT_ID}", "name": CONFIG_ENTRY_TITLE},
        ],
    }

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(config_entry.entry_id)

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert (
        response["result"]
        == {"agents": [{"agent_id": "backup.local", "name": "local"}]}
        or config_entry.state == ConfigEntryState.NOT_LOADED
    )


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
        f"{DOMAIN}.{TEST_AGENT_ID}": "Remote server error while attempting to list backups: Error message"
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
        "Failed to load backup metadata from file: backup_location/invalid.metadata.json. Expecting value: line 1 column 1 (char 0)"
        in caplog.messages
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

    # This will cause `FileNotFoundError` exception in `BackupAgentClient.iter_file() method.`
    mock_ssh_connection._sftp._mock_exists.side_effect = [True, False]
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_AGENT_BACKUP.backup_id}?agent_id={DOMAIN}.{TEST_AGENT_ID}"
    )
    assert resp.status == 404

    # This will raise `RuntimeError` causing Internal Server Error, mimicking that the SFTP setup failed.
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
    assert response["result"] == {"agent_errors": {}}

    # Called 2 times, to remove metadata and backup file.
    assert mock_ssh_connection._sftp._mock_unlink.call_count == 2


@pytest.mark.parametrize(
    ("exists_side_effect", "expected_result"),
    [
        (
            [True, False],
            {"agent_errors": {}},
        ),  # First `True` is to confirm the metadata file exists
        (
            SFTPError(0, "manual"),
            {
                "agent_errors": {
                    f"{DOMAIN}.{TEST_AGENT_ID}": f"Failed to delete backup id: {TEST_AGENT_BACKUP.backup_id}: manual"
                }
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
    assert response["result"] == {"agent_errors": {}}


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [
        listener
    ]  # make sure it's the last listener
    remove_listener()

    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data
