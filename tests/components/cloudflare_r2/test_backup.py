"""Test the Cloudflare R2 backup platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from io import StringIO
import json
from unittest.mock import ANY, AsyncMock, Mock, call, patch

from botocore.exceptions import BotoCoreError, ConnectTimeoutError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import (
    ClientSessionGenerator,
    MagicMock,
    WebSocketGenerator,
)

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.cloudflare_r2.backup import (
    CACHE_TTL,
    MULTIPART_MIN_PART_SIZE_BYTES,
    async_register_backup_agents_listener,
    suggested_filenames,
)
from homeassistant.components.cloudflare_r2.const import (
    CONF_ENDPOINT_URL,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import USER_INPUT

from tests.components.backup.common import collect_upload_events, upload_backup_via_http

MIB = 2**20
CHUNK_SIZES_MIB = (12, 12, 10, 12, 5)


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up R2 integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
        await setup_integration(hass, mock_config_entry)

        await hass.async_block_till_done()
        yield


def _get_object_response(content: bytes) -> dict[str, AsyncMock]:
    """Return a get_object response with the given body."""
    return {"Body": AsyncMock(read=AsyncMock(return_value=content))}


def _agent_backup(backup_id: str, name: str) -> AgentBackup:
    """Return a minimal backup with the given id and name."""
    return AgentBackup(
        backup_id=backup_id,
        date="2023-01-01T00:00:00+00:00",
        addons=[],
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=False,
        homeassistant_version=None,
        name=name,
        protected=False,
        size=0,
    )


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
    """Test backup agent info following config entry unload and setup."""
    client = await hass_ws_client(hass)
    local_agent = {"agent_id": "backup.local", "name": "local"}
    r2_agent = {
        "agent_id": f"{DOMAIN}.{mock_config_entry.entry_id}",
        "name": mock_config_entry.title,
    }

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agents": [local_agent, r2_agent]}

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agents": [local_agent]}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agents": [local_agent, r2_agent]}


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
    paginate = mock_client.get_paginator.return_value.paginate
    paginate.return_value.__aiter__.return_value = [{"Contents": []}]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": "random"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] is None


async def test_agents_list_backups_with_corrupted_metadata(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    test_backup: AgentBackup,
) -> None:
    """Test listing backups when one metadata file is corrupted."""
    paginate = mock_client.get_paginator.return_value.paginate
    paginate.return_value.__aiter__.return_value = [
        {
            "Contents": [
                {"Key": "valid_backup.metadata.json"},
                {"Key": "corrupted_backup.metadata.json"},
            ]
        }
    ]
    contents = {
        "valid_backup.metadata.json": json.dumps(test_backup.as_dict()).encode(),
        "corrupted_backup.metadata.json": b"{invalid json content",
    }
    mock_client.get_object.side_effect = lambda **kwargs: _get_object_response(
        contents[kwargs["Key"]]
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert [b["backup_id"] for b in response["result"]["backups"]] == [
        test_backup.backup_id
    ]
    assert (
        "Failed to process metadata file corrupted_backup.metadata.json" in caplog.text
    )


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
    assert response["result"] == {"agent_error_translations": {}, "agent_errors": {}}
    # Should delete both the tar and the metadata file
    assert mock_client.delete_object.call_count == 2


async def test_agents_delete_not_throwing_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Test agent delete backup does not throw on a backup not found."""
    paginate = mock_client.get_paginator.return_value.paginate
    paginate.return_value.__aiter__.return_value = [{"Contents": []}]

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": "random",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_error_translations": {}, "agent_errors": {}}
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
    assert "Upload failed for cloudflare_r2" in caplog.text


@pytest.mark.parametrize(
    "test_backup", [sum(CHUNK_SIZES_MIB) * MIB], indirect=True, ids=["51MiB"]
)
async def test_multipart_upload_consistent_part_sizes(
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
) -> None:
    """Test multipart parts have a constant size regardless of stream chunking."""
    resp = await upload_backup_via_http(
        await hass_client(),
        f"{DOMAIN}.{mock_config_entry.entry_id}",
        test_backup,
        [b"x" * (size * MIB) for size in CHUNK_SIZES_MIB],
    )

    assert resp.status == 201
    assert [len(c.kwargs["Body"]) for c in mock_client.upload_part.await_args_list] == [
        MULTIPART_MIN_PART_SIZE_BYTES,
        MULTIPART_MIN_PART_SIZE_BYTES,
        sum(CHUNK_SIZES_MIB) * MIB - 2 * MULTIPART_MIN_PART_SIZE_BYTES,
    ]
    assert [
        c.kwargs["PartNumber"] for c in mock_client.upload_part.await_args_list
    ] == [1, 2, 3]


@pytest.mark.usefixtures("freezer")
@pytest.mark.parametrize(
    "test_backup",
    [MULTIPART_MIN_PART_SIZE_BYTES * 2],
    indirect=True,
    ids=["large"],
)
async def test_agents_upload_on_progress(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
) -> None:
    """Test agent upload backup emits UploadBackupEvent via on_progress."""
    agent_id = f"{DOMAIN}.{mock_config_entry.entry_id}"

    with collect_upload_events(hass, agent_id) as events:
        resp = await upload_backup_via_http(
            await hass_client(), agent_id, test_backup, [b"a" * test_backup.size]
        )

    assert resp.status == 201
    assert all(e.total_bytes == test_backup.size for e in events)
    # The manager emits 0 and the backup size; later progress is debounced
    assert [e.uploaded_bytes for e in events] == [
        0,
        MULTIPART_MIN_PART_SIZE_BYTES,
        test_backup.size,
    ]


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
        "agent_error_translations": {},
        "agent_errors": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": (
                "Failed during async_delete_backup"
            )
        },
    }


async def test_cache_expiration(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the backup list is cached until CACHE_TTL expires."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()
    assert len(response["result"]["backups"]) == 1
    assert mock_client.get_paginator.call_count == 1
    assert mock_client.get_object.call_count == 1

    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()
    assert len(response["result"]["backups"]) == 1
    assert mock_client.get_paginator.call_count == 1
    assert mock_client.get_object.call_count == 1

    freezer.tick(timedelta(seconds=CACHE_TTL + 1))
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()
    assert len(response["result"]["backups"]) == 1
    assert mock_client.get_paginator.call_count == 2
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


async def test_list_backups_with_pagination(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Test listing backups when paginating through multiple pages."""
    paginate = mock_client.get_paginator.return_value.paginate
    paginate.return_value.__aiter__.return_value = [
        {"Contents": [{"Key": "backup1.metadata.json"}, {"Key": "backup1.tar"}]},
        {"Contents": [{"Key": "backup2.metadata.json"}, {"Key": "backup2.tar"}]},
    ]
    contents = {
        "backup1.metadata.json": json.dumps(
            _agent_backup("backup1", "Backup 1").as_dict()
        ).encode(),
        "backup2.metadata.json": json.dumps(
            _agent_backup("backup2", "Backup 2").as_dict()
        ).encode(),
    }
    mock_client.get_object.side_effect = lambda **kwargs: _get_object_response(
        contents[kwargs["Key"]]
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert {b["backup_id"] for b in response["result"]["backups"]} == {
        "backup1",
        "backup2",
    }


@pytest.mark.parametrize(
    "test_backup", [MULTIPART_MIN_PART_SIZE_BYTES], indirect=True, ids=["large"]
)
@pytest.mark.parametrize(
    ("config_entry_extra_data", "expected_key_prefix"),
    [
        ({"prefix": "ha/backups"}, "ha/backups/"),
        ({}, ""),
    ],
    ids=["with_prefix", "no_prefix"],
)
async def test_agent_upload_large_backup_parametrized(
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    test_backup: AgentBackup,
    expected_key_prefix: str,
) -> None:
    """Test agent upload large (multipart) backup with and without prefix."""
    resp = await upload_backup_via_http(
        await hass_client(),
        f"{DOMAIN}.{mock_config_entry.entry_id}",
        test_backup,
        # The "appendix" chunk triggers the upload of the final buffer part
        [b"a" * test_backup.size, b"appendix"],
    )

    assert resp.status == 201
    tar_filename, metadata_filename = suggested_filenames(test_backup)
    tar_key = f"{expected_key_prefix}{tar_filename}"
    mock_client.create_multipart_upload.assert_awaited_once_with(
        Bucket="test", Key=tar_key
    )
    assert mock_client.upload_part.await_args_list == [
        call(Bucket="test", Key=tar_key, PartNumber=1, UploadId="upload_id", Body=ANY),
        call(Bucket="test", Key=tar_key, PartNumber=2, UploadId="upload_id", Body=ANY),
    ]
    mock_client.complete_multipart_upload.assert_awaited_once_with(
        Bucket="test", Key=tar_key, UploadId="upload_id", MultipartUpload=ANY
    )
    mock_client.put_object.assert_awaited_once_with(
        Bucket="test", Key=f"{expected_key_prefix}{metadata_filename}", Body=ANY
    )


@pytest.mark.parametrize("test_backup", [2**20], indirect=True, ids=["small"])
@pytest.mark.parametrize(
    ("config_entry_extra_data", "expected_list_kwargs"),
    [
        ({"prefix": "ha/backups"}, {"Bucket": "test", "Prefix": "ha/backups/"}),
        ({}, {"Bucket": "test"}),
    ],
    ids=["with_prefix", "no_prefix"],
)
async def test_agent_list_backups_parametrized(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    test_backup: AgentBackup,
    expected_list_kwargs: dict[str, str],
) -> None:
    """Test agent list backups with and without prefix."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert [b["backup_id"] for b in response["result"]["backups"]] == [
        test_backup.backup_id
    ]
    mock_client.get_paginator.return_value.paginate.assert_called_once_with(
        **expected_list_kwargs
    )
