"""Test the AWS S3 backup platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from io import StringIO
import json
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, call, patch

from aiobotocore.response import StreamingBody
from aiohttp import ClientConnectionError, ClientPayloadError
from botocore.exceptions import ConnectTimeoutError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_fixture_path
from pytest_homeassistant.typing import (
    ClientSessionGenerator,
    MagicMock,
    WebSocketGenerator,
)

from homeassistant.components.aws_s3.backup import (
    CACHE_TTL,
    MULTIPART_MIN_PART_SIZE_BYTES,
    BotoCoreError,
    async_register_backup_agents_listener,
    suggested_filenames,
)
from homeassistant.components.aws_s3.const import (
    CONF_ENDPOINT_URL,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import USER_INPUT

from tests.components.backup.common import collect_upload_events, upload_backup_via_http

MIB = 2**20
CHUNK_SIZES_MIB = (12, 12, 10, 12, 5)


# Protected with password "hunter2", padded beyond the 4 MiB read buffer so the
# backup is not read to the end when checking the password or decrypting it
PROTECTED_BACKUP_DATA = (
    get_fixture_path("test_backups/c0cb53bd.tar", BACKUP_DOMAIN).read_bytes()
    + b"\0" * 12 * 2**20
)


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


def _get_object_response(content: bytes) -> dict[str, AsyncMock]:
    """Return a get_object response with the given body."""
    return {"Body": AsyncMock(read=AsyncMock(return_value=content))}


def _agent_backup(backup_id: str, name: str, date: str) -> AgentBackup:
    """Return a minimal backup with the given identity."""
    return AgentBackup(
        backup_id=backup_id,
        date=date,
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
    s3_agent = {
        "agent_id": f"{DOMAIN}.{mock_config_entry.entry_id}",
        "name": mock_config_entry.title,
    }

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"agents": [local_agent, s3_agent]}

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
    assert response["result"] == {"agents": [local_agent, s3_agent]}


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent list backups."""

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": mock_agent_backup.addons,
            "agents": {
                f"{DOMAIN}.{mock_config_entry.entry_id}": {
                    "protected": mock_agent_backup.protected,
                    "size": mock_agent_backup.size,
                }
            },
            "backup_id": mock_agent_backup.backup_id,
            "database_included": mock_agent_backup.database_included,
            "date": mock_agent_backup.date,
            "extra_metadata": mock_agent_backup.extra_metadata,
            "failed_addons": [],
            "failed_agent_ids": [],
            "failed_folders": [],
            "folders": mock_agent_backup.folders,
            "homeassistant_included": mock_agent_backup.homeassistant_included,
            "homeassistant_version": mock_agent_backup.homeassistant_version,
            "name": mock_agent_backup.name,
            "with_automatic_settings": None,
        }
    ]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent get backup."""

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "backup/details", "backup_id": mock_agent_backup.backup_id}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == {
        "addons": mock_agent_backup.addons,
        "agents": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": {
                "protected": mock_agent_backup.protected,
                "size": mock_agent_backup.size,
            }
        },
        "backup_id": mock_agent_backup.backup_id,
        "database_included": mock_agent_backup.database_included,
        "date": mock_agent_backup.date,
        "extra_metadata": mock_agent_backup.extra_metadata,
        "failed_addons": [],
        "failed_agent_ids": [],
        "failed_folders": [],
        "folders": mock_agent_backup.folders,
        "homeassistant_included": mock_agent_backup.homeassistant_included,
        "homeassistant_version": mock_agent_backup.homeassistant_version,
        "name": mock_agent_backup.name,
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
    mock_agent_backup: AgentBackup,
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
        "valid_backup.metadata.json": json.dumps(mock_agent_backup.as_dict()).encode(),
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
        mock_agent_backup.backup_id
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


@pytest.mark.parametrize(
    "backup_size",
    [
        2**20,
        MULTIPART_MIN_PART_SIZE_BYTES,
    ],
    ids=["small", "large"],
)
async def test_agents_upload_network_failure(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent upload backup with network failure."""
    client = await hass_client()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=mock_agent_backup,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=mock_agent_backup,
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


@pytest.mark.usefixtures("freezer")
@pytest.mark.parametrize(
    "backup_size", [MULTIPART_MIN_PART_SIZE_BYTES * 2], ids=["large"]
)
async def test_agents_upload_on_progress(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent upload backup emits UploadBackupEvent via on_progress."""
    agent_id = f"{DOMAIN}.{mock_config_entry.entry_id}"

    with collect_upload_events(hass, agent_id) as events:
        resp = await upload_backup_via_http(
            await hass_client(),
            agent_id,
            mock_agent_backup,
            [b"a" * mock_agent_backup.size],
        )

    assert resp.status == 201
    assert all(e.total_bytes == mock_agent_backup.size for e in events)
    # The manager emits the first (0) and last (backup size) events; the agent's
    # report of the second part is debounced
    assert [e.uploaded_bytes for e in events] == [
        0,
        MULTIPART_MIN_PART_SIZE_BYTES,
        mock_agent_backup.size,
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
    # Coordinator first refresh reads metadata (1) +
    # download reads metadata (1) + tar (1)
    assert mock_client.get_object.call_count == 3


async def test_error_during_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test the error wrapper."""
    mock_client.delete_object.side_effect = BotoCoreError

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": mock_agent_backup.backup_id,
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
    # The coordinator's first refresh also lists the bucket
    mock_client.reset_mock()

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
    backup1 = _agent_backup("backup1", "Backup 1", "2023-01-01T00:00:00+00:00")
    backup2 = _agent_backup("backup2", "Backup 2", "2023-01-02T00:00:00+00:00")
    paginate = mock_client.get_paginator.return_value.paginate
    paginate.return_value.__aiter__.return_value = [
        {"Contents": [{"Key": "backup1.metadata.json"}, {"Key": "backup1.tar"}]},
        {"Contents": [{"Key": "backup2.metadata.json"}, {"Key": "backup2.tar"}]},
    ]
    contents = {
        "backup1.metadata.json": json.dumps(backup1.as_dict()).encode(),
        "backup2.metadata.json": json.dumps(backup2.as_dict()).encode(),
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
    ("config_entry_extra_data", "expected_paginate_extra_kwargs"),
    [
        ({"prefix": "backups/home"}, {"Prefix": "backups/home/"}),
        ({}, {}),
    ],
    ids=["with_prefix", "no_prefix"],
)
async def test_agent_list_backups_parametrized(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_agent_backup: AgentBackup,
    config_entry_extra_data: dict,
    expected_paginate_extra_kwargs: dict,
) -> None:
    """Test agent list backups with and without prefix."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}

    # Verify pagination call with expected parameters
    mock_client.get_paginator.return_value.paginate.assert_called_with(
        **{"Bucket": "test"} | expected_paginate_extra_kwargs
    )


@pytest.mark.parametrize(
    ("config_entry_extra_data", "expected_key_prefix"),
    [
        ({"prefix": "backups/home"}, "backups/home/"),
        ({}, ""),
    ],
    ids=["with_prefix", "no_prefix"],
)
async def test_agent_delete_backup_parametrized(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    expected_key_prefix: str,
) -> None:
    """Test agent delete backup with and without prefix."""
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

    tar_filename, metadata_filename = suggested_filenames(mock_agent_backup)

    expected_tar_key = f"{expected_key_prefix}{tar_filename}"
    expected_metadata_key = f"{expected_key_prefix}{metadata_filename}"

    mock_client.delete_object.assert_any_call(Bucket="test", Key=expected_tar_key)
    mock_client.delete_object.assert_any_call(Bucket="test", Key=expected_metadata_key)


@pytest.mark.parametrize(
    ("config_entry_extra_data", "expected_key_prefix"),
    [
        ({"prefix": "backups/home"}, "backups/home/"),
        ({}, ""),
    ],
    ids=["with_prefix", "no_prefix"],
)
async def test_agent_upload_small_backup_parametrized(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    expected_key_prefix: str,
) -> None:
    """Test agent upload small backup with and without prefix."""
    resp = await upload_backup_via_http(
        await hass_client(),
        f"{DOMAIN}.{mock_config_entry.entry_id}",
        mock_agent_backup,
        # The "appendix" chunk triggers the upload of the final buffer part
        [b"a" * mock_agent_backup.size, b"appendix"],
    )

    assert resp.status == 201
    assert f"Uploading backup {mock_agent_backup.backup_id}" in caplog.text
    assert mock_client.create_multipart_upload.await_count == 0
    assert mock_client.upload_part.await_count == 0
    assert mock_client.complete_multipart_upload.await_count == 0
    assert mock_client.put_object.await_count == 2
    tar_filename, metadata_filename = suggested_filenames(mock_agent_backup)
    mock_client.put_object.assert_has_calls(
        [
            call(Bucket="test", Key=f"{expected_key_prefix}{tar_filename}", Body=ANY),
            call(
                Bucket="test",
                Key=f"{expected_key_prefix}{metadata_filename}",
                Body=ANY,
            ),
        ]
    )


@pytest.mark.parametrize("backup_size", [MULTIPART_MIN_PART_SIZE_BYTES], ids=["large"])
@pytest.mark.parametrize(
    ("config_entry_extra_data", "expected_key_prefix"),
    [
        ({"prefix": "backups/home"}, "backups/home/"),
        ({}, ""),
    ],
    ids=["with_prefix", "no_prefix"],
)
async def test_agent_upload_large_backup_parametrized(
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    expected_key_prefix: str,
) -> None:
    """Test agent upload large (multipart) backup with and without prefix."""
    resp = await upload_backup_via_http(
        await hass_client(),
        f"{DOMAIN}.{mock_config_entry.entry_id}",
        mock_agent_backup,
        # The "appendix" chunk triggers the upload of the final buffer part
        [b"a" * mock_agent_backup.size, b"appendix"],
    )

    assert resp.status == 201
    tar_filename, metadata_filename = suggested_filenames(mock_agent_backup)

    tar_key = f"{expected_key_prefix}{tar_filename}"
    metadata_key = f"{expected_key_prefix}{metadata_filename}"

    assert f"Uploading backup {mock_agent_backup.backup_id}" in caplog.text
    assert mock_client.create_multipart_upload.await_count == 1
    assert mock_client.upload_part.await_count == 2
    assert mock_client.complete_multipart_upload.await_count == 1
    assert mock_client.put_object.await_count == 1
    mock_client.create_multipart_upload.assert_called_with(Bucket="test", Key=tar_key)
    mock_client.upload_part.assert_has_calls(
        [
            call(
                Bucket="test",
                Key=tar_key,
                PartNumber=1,
                UploadId="upload_id",
                Body=ANY,
            ),
            call(
                Bucket="test",
                Key=tar_key,
                PartNumber=2,
                UploadId="upload_id",
                Body=ANY,
            ),
        ]
    )
    mock_client.complete_multipart_upload.assert_called_with(
        Bucket="test",
        Key=tar_key,
        UploadId="upload_id",
        MultipartUpload=ANY,
    )
    mock_client.put_object.assert_called_with(Bucket="test", Key=metadata_key, Body=ANY)


@pytest.mark.parametrize("backup_size", [sum(CHUNK_SIZES_MIB) * MIB], ids=["51MiB"])
async def test_multipart_upload_consistent_part_sizes(
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test multipart parts have a constant size regardless of stream chunking."""
    resp = await upload_backup_via_http(
        await hass_client(),
        f"{DOMAIN}.{mock_config_entry.entry_id}",
        mock_agent_backup,
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


@pytest.mark.parametrize(
    ("config_entry_extra_data", "expected_key_prefix"),
    [
        ({"prefix": "backups/home"}, "backups/home/"),
        ({}, ""),
    ],
    ids=["with_prefix", "no_prefix"],
)
async def test_agent_download_backup_parametrized(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    expected_key_prefix: str,
) -> None:
    """Test agent download backup with and without prefix."""
    client = await hass_client()
    backup_id = "23e64aec"

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 200
    assert await resp.content.read() == b"backup data"

    tar_filename, _ = suggested_filenames(mock_agent_backup)

    expected_tar_key = f"{expected_key_prefix}{tar_filename}"

    mock_client.get_object.assert_any_call(Bucket="test", Key=expected_tar_key)


@pytest.fixture
def downloaded_bodies(mock_client: MagicMock) -> list[StreamingBody]:
    """Return the bodies of downloaded backup archives."""
    bodies: list[StreamingBody] = []
    get_object = mock_client.get_object.side_effect

    def get_object_and_track(**kwargs: Any) -> dict[str, Any]:
        response = get_object(**kwargs)
        if kwargs["Key"].endswith(".tar"):
            bodies.append(response["Body"])
        return response

    mock_client.get_object.side_effect = get_object_and_track
    return bodies


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
async def test_can_decrypt_on_download_closes_body(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    downloaded_bodies: list[StreamingBody],
    password: str,
    success: bool,
) -> None:
    """Test the download is closed after checking the password of a backup."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/can_decrypt_on_download",
            "backup_id": "23e64aec",
            "agent_id": f"{DOMAIN}.{mock_config_entry.entry_id}",
            "password": password,
        }
    )
    assert (await client.receive_json())["success"] is success

    assert len(downloaded_bodies) == 1
    downloaded_bodies[0].close.assert_called_once()


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
async def test_agents_download_closes_body(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    downloaded_bodies: list[StreamingBody],
    query: str,
) -> None:
    """Test the download is closed when the backup is downloaded."""
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/23e64aec?agent_id={DOMAIN}.{mock_config_entry.entry_id}{query}"
    )
    assert resp.status == 200
    await resp.read()

    assert len(downloaded_bodies) == 1
    downloaded_bodies[0].close.assert_called_once()


async def test_agents_download_closes_body_on_read_error(
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the download is closed when reading the backup fails."""
    reader = asyncio.StreamReader()
    reader.set_exception(ClientConnectionError())
    response = MagicMock(content=reader)
    get_object = mock_client.get_object.side_effect
    mock_client.get_object.side_effect = lambda **kwargs: (
        {"Body": StreamingBody(response, "11")}
        if kwargs["Key"].endswith(".tar")
        else get_object(**kwargs)
    )
    client = await hass_client()

    resp = await client.get(
        f"/api/backup/download/23e64aec?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    with pytest.raises(ClientPayloadError):
        await resp.read()

    response.close.assert_called_once()
