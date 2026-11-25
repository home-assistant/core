"""Test the Seafile backup agent."""

import asyncio
from collections.abc import AsyncGenerator
from io import StringIO
import json
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, _Call, call, patch

from aiohttp import ClientPayloadError
from aioseafile import (
    DirectoryListing,
    SeafileConnectionError,
    SeafileNotFoundError,
    SeafileTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator

from homeassistant.components.backup import DATA_MANAGER, DOMAIN as BACKUP_DOMAIN
from homeassistant.components.seafile.backup import (
    CACHE_TTL,
    UPLOAD_CHUNK_SIZE,
    async_register_backup_agents_listener,
)
from homeassistant.components.seafile.const import (
    CONF_BACKUP,
    CONF_BACKUP_PATH,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import (
    BACKUP_BASE_NAME,
    BACKUP_PATH,
    LIBRARY_ID,
    SUBENTRY_ID,
    TEST_BACKUP,
    backup_listing,
    stream,
)

from tests.components.backup.common import (
    collect_upload_events,
    flush_upload_progress,
    upload_backup_via_http,
)

AGENT_ID = f"{DOMAIN}.{SUBENTRY_ID}"


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up the backup and Seafile integrations."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
        await setup_integration(hass, mock_config_entry)
        yield


async def _ws_request(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, message: dict
) -> dict:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(message)
    response = await client.receive_json()
    assert response["success"]
    return response["result"]


async def test_agents_info(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a library that stores backups is a backup agent."""
    result = await _ws_request(hass, hass_ws_client, {"type": "backup/agents/info"})

    assert result["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
        {
            "agent_id": AGENT_ID,
            "name": "user@example.com (seafile.example.com) - Documents",
        },
    ]


async def test_agent_disabled(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning backups off for a library removes its agent."""
    subentry = mock_config_entry.subentries[SUBENTRY_ID]
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data={**subentry.data, CONF_BACKUP: False}
    )
    await hass.async_block_till_done()

    result = await _ws_request(hass, hass_ws_client, {"type": "backup/agents/info"})
    assert result["agents"] == [{"agent_id": "backup.local", "name": "local"}]


async def test_agents_removed_on_unload(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the agent is removed when the entry is unloaded."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await _ws_request(hass, hass_ws_client, {"type": "backup/agents/info"})
    assert result["agents"] == [{"agent_id": "backup.local", "name": "local"}]


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_seafile_client: AsyncMock,
) -> None:
    """Test listing reads the metadata files in the backup folder."""
    result = await _ws_request(hass, hass_ws_client, {"type": "backup/info"})

    assert result["agent_errors"] == {}
    assert [backup["backup_id"] for backup in result["backups"]] == ["23e64aec"]
    assert result["backups"][0]["agents"] == {
        AGENT_ID: {"protected": False, "size": 34519040}
    }
    mock_seafile_client.get_directory.assert_called_with(
        LIBRARY_ID, BACKUP_PATH, entry_type=ANY
    )
    mock_seafile_client.download_file.assert_called_with(
        LIBRARY_ID, f"{BACKUP_PATH}/{BACKUP_BASE_NAME}_meta.json"
    )


@pytest.mark.parametrize(
    ("method", "attribute", "value"),
    [
        pytest.param(
            "get_directory",
            "side_effect",
            SeafileNotFoundError,
            id="folder_not_created_yet",
        ),
        pytest.param(
            "download_file",
            "side_effect",
            lambda *_args, **_kwargs: stream(b"not json"),
            id="invalid_metadata",
        ),
        pytest.param(
            "download_file",
            "side_effect",
            SeafileNotFoundError,
            id="metadata_deleted_while_listing",
        ),
        pytest.param(
            "get_directory",
            "return_value",
            backup_listing(f"{BACKUP_BASE_NAME}.tar"),
            id="metadata_missing",
        ),
        pytest.param(
            "get_directory",
            "return_value",
            backup_listing(f"{BACKUP_BASE_NAME}_meta.json"),
            id="backup_file_missing",
        ),
    ],
)
async def test_agents_list_backups_empty(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_seafile_client: AsyncMock,
    method: str,
    attribute: str,
    value: object,
) -> None:
    """Test the folder is listed as empty when it holds no complete backups."""
    setattr(getattr(mock_seafile_client, method), attribute, value)

    result = await _ws_request(hass, hass_ws_client, {"type": "backup/info"})

    assert result["agent_errors"] == {}
    assert result["backups"] == []


async def test_agents_get_backup(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting a backup."""
    result = await _ws_request(
        hass,
        hass_ws_client,
        {"type": "backup/details", "backup_id": TEST_BACKUP.backup_id},
    )

    assert result["agent_errors"] == {}
    assert result["backup"]["backup_id"] == TEST_BACKUP.backup_id
    assert result["backup"]["agents"] == {
        AGENT_ID: {"protected": False, "size": 34519040}
    }


async def test_agents_get_backup_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting a backup that doesn't exist."""
    result = await _ws_request(
        hass, hass_ws_client, {"type": "backup/details", "backup_id": "random"}
    )

    assert result["agent_errors"] == {}
    assert result["backup"] is None


async def _upload(hass_client: ClientSessionGenerator) -> int:
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
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={AGENT_ID}",
            data={"file": StringIO("test")},
        )
    return resp.status


async def test_agents_upload_to_library_root(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the library root as backup folder is not created first."""
    subentry = mock_config_entry.subentries[SUBENTRY_ID]
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data={**subentry.data, CONF_BACKUP_PATH: "/"}
    )
    await hass.async_block_till_done()

    assert await _upload(hass_client) == 201
    mock_seafile_client.create_directory.assert_not_called()
    assert mock_seafile_client.upload_file.await_args_list[0].args[1] == "/"


@pytest.mark.parametrize(
    ("listing", "expected_deletes"),
    [
        pytest.param(
            backup_listing(),
            [call(LIBRARY_ID, BACKUP_PATH, [f"{BACKUP_BASE_NAME}.tar"])],
            id="new_backup",
        ),
        pytest.param(
            backup_listing(f"{BACKUP_BASE_NAME}.tar", f"{BACKUP_BASE_NAME}_meta.json"),
            [],
            id="replaced_backup",
        ),
    ],
)
async def test_agents_upload_metadata_failed(
    hass_client: ClientSessionGenerator,
    mock_seafile_client: AsyncMock,
    listing: DirectoryListing,
    expected_deletes: list[_Call],
) -> None:
    """Test a new backup file is removed when its metadata can't be stored.

    An existing backup that was uploaded again is kept.
    """
    mock_seafile_client.get_directory.return_value = listing
    mock_seafile_client.upload_file.side_effect = [None, SeafileConnectionError]

    await _upload(hass_client)

    assert mock_seafile_client.delete_items.await_args_list == expected_deletes


async def test_agents_upload(
    hass_client: ClientSessionGenerator,
    mock_seafile_client: AsyncMock,
) -> None:
    """Test uploading writes the backup in chunks, then its metadata."""
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
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        resp = await client.post(
            f"/api/backup/upload?agent_id={AGENT_ID}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    mock_seafile_client.create_directory.assert_awaited_once_with(
        LIBRARY_ID, BACKUP_PATH
    )
    tar_call, metadata_call = mock_seafile_client.upload_file.await_args_list
    assert tar_call.args[:3] == (LIBRARY_ID, BACKUP_PATH, f"{BACKUP_BASE_NAME}.tar")
    assert tar_call.kwargs == {
        "size": TEST_BACKUP.size,
        "replace": True,
        "chunk_size": UPLOAD_CHUNK_SIZE,
        "on_progress": ANY,
    }
    assert metadata_call.args[:3] == (
        LIBRARY_ID,
        BACKUP_PATH,
        f"{BACKUP_BASE_NAME}_meta.json",
    )
    assert json.loads(metadata_call.args[3]) == TEST_BACKUP.as_dict()


async def test_agents_upload_on_progress(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_seafile_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the upload progress of the backup file is reported."""

    async def mock_upload_file(*args: Any, **kwargs: Any) -> None:
        # The metadata upload doesn't report progress
        on_progress = kwargs.get("on_progress", lambda _: None)
        on_progress(1)
        # Report each value in its own event
        flush_upload_progress(hass, freezer)
        on_progress(3)

    mock_seafile_client.upload_file.side_effect = mock_upload_file

    with collect_upload_events(hass, AGENT_ID) as events:
        resp = await upload_backup_via_http(await hass_client(), AGENT_ID, TEST_BACKUP)

    assert resp.status == 201
    # The manager emits the first (0) and last (backup size) events
    assert [event.uploaded_bytes for event in events] == [0, 1, 3, TEST_BACKUP.size]


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_seafile_client: AsyncMock,
) -> None:
    """Test downloading streams the backup file."""
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={AGENT_ID}"
    )

    assert resp.status == 200
    assert await resp.content.read() == b"backup data"
    mock_seafile_client.get_download_link.assert_awaited_once_with(
        LIBRARY_ID, f"{BACKUP_PATH}/{BACKUP_BASE_NAME}.tar"
    )


async def test_agents_download_not_found(
    hass_client: ClientSessionGenerator,
    mock_seafile_client: AsyncMock,
) -> None:
    """Test downloading a backup that doesn't exist."""
    client = await hass_client()
    resp = await client.get(f"/api/backup/download/random?agent_id={AGENT_ID}")

    assert resp.status == 404
    mock_seafile_client.get_download_link.assert_not_called()


@pytest.mark.parametrize("error", [SeafileConnectionError, SeafileTimeoutError])
async def test_agents_download_stream_error(
    hass_client: ClientSessionGenerator,
    mock_seafile_client: AsyncMock,
    error: type[Exception],
) -> None:
    """Test an error while the backup is streamed breaks off the download."""

    async def broken_stream(*_args: object, **_kwargs: object) -> AsyncGenerator[bytes]:
        yield b"backup "
        raise error

    mock_seafile_client.download.side_effect = broken_stream
    client = await hass_client()
    resp = await client.get(
        f"/api/backup/download/{TEST_BACKUP.backup_id}?agent_id={AGENT_ID}"
    )

    assert resp.status == 200
    with pytest.raises(ClientPayloadError):
        await resp.content.read()


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_seafile_client: AsyncMock,
) -> None:
    """Test deleting removes the backup and its metadata."""
    result = await _ws_request(
        hass,
        hass_ws_client,
        {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id},
    )

    assert result == {"agent_error_translations": {}, "agent_errors": {}}
    mock_seafile_client.delete_items.assert_awaited_once_with(
        LIBRARY_ID,
        BACKUP_PATH,
        [f"{BACKUP_BASE_NAME}.tar", f"{BACKUP_BASE_NAME}_meta.json"],
    )


async def test_agents_list_cached(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_seafile_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the listing is cached and kept up to date by deletes."""
    await _ws_request(hass, hass_ws_client, {"type": "backup/info"})
    await _ws_request(
        hass,
        hass_ws_client,
        {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id},
    )
    result = await _ws_request(hass, hass_ws_client, {"type": "backup/info"})

    assert result["backups"] == []
    assert mock_seafile_client.get_directory.await_count == 1

    freezer.tick(CACHE_TTL + 1)
    result = await _ws_request(hass, hass_ws_client, {"type": "backup/info"})

    # The mocked server still lists the backup.
    assert len(result["backups"]) == 1
    assert mock_seafile_client.get_directory.await_count == 2


async def test_agents_list_finishing_after_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_seafile_client: AsyncMock,
) -> None:
    """Test a listing that finishes after a delete doesn't bring the backup back."""
    listing = mock_seafile_client.get_directory.return_value
    started = asyncio.Event()
    release = asyncio.Event()

    async def listing_once_released(*args: Any, **kwargs: Any) -> DirectoryListing:
        # Only the first listing waits, the one for the delete returns at once.
        if mock_seafile_client.get_directory.await_count == 1:
            started.set()
            await release.wait()
        return listing

    mock_seafile_client.get_directory.side_effect = listing_once_released
    agent = hass.data[DATA_MANAGER].backup_agents[AGENT_ID]
    slow_list = hass.async_create_task(agent.async_list_backups())
    await started.wait()

    await agent.async_delete_backup(TEST_BACKUP.backup_id)
    release.set()
    # The listing started before the delete, so it still contains the backup.
    assert len(await slow_list) == 1

    result = await _ws_request(hass, hass_ws_client, {"type": "backup/info"})
    assert result["backups"] == []
    assert mock_seafile_client.get_directory.await_count == 2


async def test_agents_delete_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_seafile_client: AsyncMock,
) -> None:
    """Test deleting a backup that doesn't exist does not fail."""
    result = await _ws_request(
        hass, hass_ws_client, {"type": "backup/delete", "backup_id": "random"}
    )

    assert result == {"agent_error_translations": {}, "agent_errors": {}}
    mock_seafile_client.delete_items.assert_not_called()


@pytest.mark.parametrize(
    ("error", "message", "translation_key"),
    [
        pytest.param(
            SeafileConnectionError,
            "Backup operation failed",
            "agent_operation_failed",
            id="failed",
        ),
        pytest.param(
            SeafileTimeoutError,
            "Backup operation timed out",
            "agent_operation_timed_out",
            id="timed_out",
        ),
    ],
)
async def test_agents_delete_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_seafile_client: AsyncMock,
    error: type[Exception],
    message: str,
    translation_key: str,
) -> None:
    """Test Seafile errors are reported as backup agent errors."""
    mock_seafile_client.delete_items.side_effect = error

    result = await _ws_request(
        hass,
        hass_ws_client,
        {"type": "backup/delete", "backup_id": TEST_BACKUP.backup_id},
    )

    assert result == {
        "agent_error_translations": {
            AGENT_ID: {
                "translation_domain": "backup",
                "translation_key": translation_key,
                "translation_placeholders": None,
            }
        },
        "agent_errors": {AGENT_ID: message},
    }


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test the listener store is removed with the last listener."""
    # Start without the listener of the backup integration.
    hass.data.pop(DATA_BACKUP_AGENT_LISTENERS)
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    assert hass.data[DATA_BACKUP_AGENT_LISTENERS] == [listener]
    remove_listener()
    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data
