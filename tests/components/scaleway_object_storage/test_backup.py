"""Tests for the Scaleway Object Storage BackupAgent implementation."""

from collections.abc import AsyncGenerator, Iterable
import hashlib
from io import StringIO
import json
from math import ceil
import random
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

from aiohttp import ClientConnectionError
import pytest
import pytest_asyncio

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.scaleway_object_storage import (
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    exceptions,
)
from homeassistant.components.scaleway_object_storage.backup import (
    ScalewayBackupAgent,
    _Part,
    _ProgressTracker,
    async_register_backup_agents_listener,
)
from homeassistant.components.scaleway_object_storage.const import (
    CONF_BUCKET,
    HEADER_CONTENT_DISPOSITION,
    HEADER_CONTENT_TYPE,
    HEADER_METADATA,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MockS3ResponseFactory

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest_asyncio.fixture(autouse=True)
async def set_up_backup_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_s3_client: AsyncMock,
) -> AsyncGenerator[None]:
    """Sets up the Scaleway Object Storage integration."""
    assert await async_setup_component(hass, BACKUP_DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.scaleway_object_storage.helpers.check_connection",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    yield


async def _split_random_chunks(
    data: bytes, *, max_chunk_size: int
) -> AsyncGenerator[bytes]:
    """Split the given bytes into randomly-sized chunks."""
    position = 0
    with memoryview(data) as view:
        while position < len(data):
            size = random.randint(1, max_chunk_size)
            end = min(len(data), position + size)
            yield view[position:end].tobytes()
            position = end


async def test_read_fixed_sized_parts() -> None:
    """Unit test for ScalewayBackupAgent._read_fixed_sized_parts function."""
    data = random.randbytes(1200)

    part_generator = ScalewayBackupAgent._read_fixed_sized_parts(
        _split_random_chunks(data, max_chunk_size=33), part_size=17
    )
    parts = [part async for part in part_generator]

    # Assert we got the expected amount of parts
    expected_parts = ceil(1200 / 17)
    assert len(parts) == expected_parts

    # Assert all parts except for the last are of equal size
    assert all(part.size == 17 for part in parts[:-1])

    # Assert that the concatenated data of all parts matched the input data
    received_data = bytearray()
    for part in parts:
        received_data.extend(part.data)

    assert bytes(received_data) == data


async def _wrap_as_generator[T](items: Iterable[T]) -> AsyncGenerator[T]:
    """Wrap an ordinary iterable as an AsyncGenerator."""
    for item in items:
        yield item


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
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent list backups."""

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.helpers.list_objects",
            # Including a fake object key in the list to simulate an object that exists during
            # listing but is gone when reading metadata.
            return_value=_wrap_as_generator(
                [mock_agent_backup_object_key, "nonexistent-object"]
            ),
        ),
    ):
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


async def test_agents_list_backups_missing_metadata(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
) -> None:
    """Test agent list backups with missing metadata."""

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.helpers.list_objects",
            return_value=_wrap_as_generator([mock_agent_backup_object_key]),
        ),
        patch(
            "homeassistant.components.scaleway_object_storage.helpers.read_object_metadata",
            side_effect=exceptions.MissingMetadataException(
                object_key=mock_agent_backup_object_key
            ),
        ),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == []


async def test_agents_list_backups_network_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent list backups when Scaleway is unreachable."""

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.list_objects",
        side_effect=exceptions.ScalewayConnectionError(),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{mock_config_entry.entry_id}": "Failed to connect",
    }


async def test_agents_list_backups_server_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent list backups when Scaleway service is degraded."""

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.list_objects",
        side_effect=exceptions.ServerUnavailableError(),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{mock_config_entry.entry_id}": "Scaleway service is temporarily unavailable",
    }


async def test_agents_list_backups_object_permission_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    agent_id: str,
) -> None:
    """Test agent list backups when Scaleway service is degraded."""

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.helpers.list_objects",
            return_value=_wrap_as_generator([mock_agent_backup_object_key]),
        ),
        patch(
            "homeassistant.components.scaleway_object_storage.helpers.read_object_metadata",
            side_effect=exceptions.InvalidAuthException(),
        ),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        agent_id: "Invalid authentication",
    }


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    mock_read_object_metadata: AsyncMock,
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


async def test_agents_get_backup_network_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent get backup when Scaleway is unreachable."""

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.read_object_metadata",
        side_effect=exceptions.ScalewayConnectionError(),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": mock_agent_backup.backup_id}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{mock_config_entry.entry_id}": "Failed to connect",
    }


async def test_agents_get_backup_server_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent get backup when Scaleway service is degraded."""

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.read_object_metadata",
        side_effect=exceptions.ServerUnavailableError(),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "backup/details", "backup_id": mock_agent_backup.backup_id}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {
        f"{DOMAIN}.{mock_config_entry.entry_id}": "Scaleway service is temporarily unavailable",
    }


async def test_agents_get_backup_does_not_throw_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent get backup does not throw on a backup not found."""

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": "random"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] is None


async def test_agents_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent delete backup."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=200)
    mock_s3_client.delete.return_value = mock_response_context

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": mock_agent_backup.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"agent_errors": {}}
    assert mock_s3_client.delete.call_count == 1
    assert mock_response.release.call_count == 1


async def test_agents_delete_network_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_s3_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test agent delete backup when Scaleway is unreachable."""
    mock_s3_client.delete.side_effect = ClientConnectionError()

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
        "agent_errors": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": "Failed to connect",
        }
    }
    assert mock_s3_client.delete.call_count == 1


@pytest.mark.parametrize(
    "status_code",
    [
        500,
        502,
        504,
    ],
)
async def test_agents_delete_server_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup: AgentBackup,
    status_code: int,
) -> None:
    """Test agent delete backup when Scaleway service is degraded."""
    mock_response, mock_response_context = mock_s3_response_factory(
        status_code=status_code
    )
    mock_s3_client.delete.return_value = mock_response_context

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
        "agent_errors": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": "Scaleway service is temporarily unavailable",
        }
    }
    assert mock_s3_client.delete.call_count == 1
    assert mock_response.release.call_count == 1


async def test_agents_delete_not_throwing_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
) -> None:
    """Test agent delete backup."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=404)
    mock_s3_client.delete.return_value = mock_response_context

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
    assert mock_s3_client.delete.call_count == 1
    assert mock_response.release.call_count == 1


async def test_agents_download(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent download backup."""
    backup_data = random.randbytes(1000)
    mock_response, mock_response_context = mock_s3_response_factory(status_code=200)
    mock_response.content.iter_any.return_value = _split_random_chunks(
        backup_data, max_chunk_size=32
    )

    mock_s3_client.get.return_value = mock_response_context

    client = await hass_client()
    backup_id = mock_agent_backup.backup_id

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 200
    assert await resp.content.read() == backup_data
    assert mock_response.release.call_count == 1


async def test_agents_download_not_found(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent download backup for missing object."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=404)
    mock_s3_client.get.return_value = mock_response_context

    client = await hass_client()
    backup_id = mock_agent_backup.backup_id

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 404
    assert mock_response.release.call_count == 1


async def test_agents_download_server_error(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent download backup with degraded Scaleway service."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=504)
    mock_s3_client.get.return_value = mock_response_context

    client = await hass_client()
    backup_id = mock_agent_backup.backup_id

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 500
    assert mock_response.release.call_count == 1


async def test_agents_download_network_error(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_s3_client: MagicMock,
    mock_agent_backup: AgentBackup,
    mock_read_object_metadata: AsyncMock,
) -> None:
    """Test agent download backup with network error."""
    mock_s3_client.get.side_effect = ClientConnectionError()

    client = await hass_client()
    backup_id = mock_agent_backup.backup_id

    resp = await client.get(
        f"/api/backup/download/{backup_id}?agent_id={DOMAIN}.{mock_config_entry.entry_id}"
    )
    assert resp.status == 500


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [
        listener
    ]  # make sure it's the last listener
    remove_listener()

    assert DATA_BACKUP_AGENT_LISTENERS not in hass.data


async def test_progress_tracker() -> None:
    """Test the ProgressTracker helper."""
    parts = [
        _Part.from_data(b"testdata"),
        _Part.from_data(b"moretestdata"),
    ]

    updates: list[int] = []

    def on_progress(*, bytes_uploaded: int, **kwargs: Any) -> None:
        updates.append(bytes_uploaded)

    tracker = _ProgressTracker(on_progress)
    assert updates == []

    await tracker.report_done(parts[0])
    assert updates == [parts[0].size]

    await tracker.report_done(parts[1])
    assert updates == [parts[0].size, sum(part.size for part in parts)]


async def _upload_backup(
    hass_client: ClientSessionGenerator,
    agent_id: str,
    agent_backup: AgentBackup,
) -> None:
    """Perform a backup upload with the necessary mocks set up."""
    client = await hass_client()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=agent_backup,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=agent_backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        byte_chunks = [
            chunk
            async for chunk in _split_random_chunks(
                random.randbytes(agent_backup.size), max_chunk_size=64
            )
        ]
        # Append empty last chunk to signal end of stream
        byte_chunks.append(b"")

        mocked_open.return_value.read = MagicMock(
            side_effect=byte_chunks,
        )

        resp = await client.post(
            f"/api/backup/upload?agent_id={agent_id}",
            data={"file": StringIO("test")},
        )
    assert resp.status == 201


async def test_simple_upload(
    hass_client: ClientSessionGenerator,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    agent_id,
) -> None:
    """Test upload smaller than the multipart threshold."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=200)
    mock_s3_client.put.return_value = mock_response_context

    await _upload_backup(
        hass_client=hass_client,
        agent_id=agent_id,
        agent_backup=mock_agent_backup,
    )

    mock_s3_client.put.assert_has_calls(
        [
            call(
                object_name=mock_agent_backup_object_key,
                data=ANY,
                data_length=mock_agent_backup.size,
                headers={
                    HEADER_METADATA: json.dumps(mock_agent_backup.as_dict()),
                    HEADER_CONTENT_TYPE: "application/x-tar",
                    HEADER_CONTENT_DISPOSITION: 'attachment; filename="Core_2024.12.0.dev0_2024-11-22_11.48_48727189.tar"',
                },
            ),
        ]
    )
    assert mock_response.release.call_count == 1


async def test_simple_upload_network_error(
    hass_client: ClientSessionGenerator,
    mock_s3_client: MagicMock,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    agent_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload smaller than the multipart threshold with a network error."""
    mock_s3_client.put.side_effect = ClientConnectionError()

    await _upload_backup(
        hass_client=hass_client,
        agent_id=agent_id,
        agent_backup=mock_agent_backup,
    )

    assert mock_s3_client.put.call_count == 1
    assert f"Upload failed for {agent_id}: Failed to connect" in caplog.text


async def test_simple_upload_server_error(
    hass_client: ClientSessionGenerator,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    agent_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test upload smaller than the multipart threshold with a server error."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=500)
    mock_s3_client.put.return_value = mock_response_context

    await _upload_backup(
        hass_client=hass_client,
        agent_id=agent_id,
        agent_backup=mock_agent_backup,
    )

    assert mock_s3_client.put.call_count == 1
    assert mock_response.release.call_count == 1
    assert (
        f"Upload failed for {agent_id}: Scaleway service is temporarily unavailable"
        in caplog.text
    )


class _BytesOfLength:
    """Custom matcher for mock call validation to validate bytes args have a specific length."""

    def __init__(self, length: int) -> None:
        self._length = length

    def __eq__(self, other: object) -> bool:
        return isinstance(other, bytes) and len(other) == self._length


async def test_multipart_upload(
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    agent_id,
) -> None:
    """Test multipart upload."""
    upload_id = "cafe"
    post_response, post_response_context = mock_s3_response_factory(status_code=200)
    post_response.read.return_value = f"""<?xml version="1.0" encoding="UTF-8"?>
    <InitiateMultipartUploadResult>
       <Bucket>{mock_config_entry.data[CONF_BUCKET]}</Bucket>
       <Key>{mock_agent_backup_object_key}</Key>
       <UploadId>{upload_id}</UploadId>
    </InitiateMultipartUploadResult>
    """.encode()
    mock_s3_client.post.return_value = post_response_context

    put_response, put_response_context = mock_s3_response_factory(status_code=200)
    put_response.headers = {
        "Etag": '"some-e-tag"',
    }
    mock_s3_client.put.return_value = put_response_context

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_MIN_SIZE",
            new=0,
        ),
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_PART_SIZE",
            new=512,
        ),
    ):
        await _upload_backup(
            hass_client=hass_client,
            agent_id=agent_id,
            agent_backup=mock_agent_backup,
        )

    mock_s3_client.post.assert_has_calls(
        [
            # First call creates the multipart upload
            call(
                mock_agent_backup_object_key,
                params={
                    "uploads": 1,
                },
                content_sha256=hashlib.sha256(b"").hexdigest(),
                headers={
                    HEADER_METADATA: json.dumps(mock_agent_backup.as_dict()),
                    HEADER_CONTENT_TYPE: "application/x-tar",
                    HEADER_CONTENT_DISPOSITION: 'attachment; filename="Core_2024.12.0.dev0_2024-11-22_11.48_48727189.tar"',
                },
            ),
            # Second call completes the multipart upload after all parts have been uploaded
            call(
                mock_agent_backup_object_key,
                params={
                    "uploadId": "cafe",
                },
                headers={
                    HEADER_CONTENT_TYPE: "text/xml",
                },
                data=ANY,
                content_sha256=ANY,
            ),
        ]
    )

    mock_s3_client.put.assert_has_calls(
        [
            call(
                mock_agent_backup_object_key,
                params={
                    "uploadId": "cafe",
                    "partNumber": 1,
                },
                data=_BytesOfLength(512),
                content_sha256=ANY,
            ),
            call(
                mock_agent_backup_object_key,
                params={
                    "uploadId": "cafe",
                    "partNumber": 2,
                },
                data=_BytesOfLength(512),
                content_sha256=ANY,
            ),
            call(
                mock_agent_backup_object_key,
                params={
                    "uploadId": "cafe",
                    "partNumber": 3,
                },
                # The mock_agent_backup has 1234 bytes, so the third part is the remainder.
                data=_BytesOfLength(mock_agent_backup.size - 1024),
                content_sha256=ANY,
            ),
        ],
        any_order=True,
    )


async def test_multipart_upload_creation_network_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    agent_id: str,
    mock_s3_client: MagicMock,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test multipart upload with a network error during upload creation."""
    mock_s3_client.post.side_effect = ClientConnectionError()

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_MIN_SIZE",
            new=0,
        ),
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_PART_SIZE",
            new=512,
        ),
    ):
        await _upload_backup(
            hass_client=hass_client,
            agent_id=agent_id,
            agent_backup=mock_agent_backup,
        )

    await hass.async_block_till_done()

    assert f"Upload failed for {agent_id}: Failed to connect" in caplog.text


async def test_multipart_upload_part_upload_network_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    agent_id: str,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test multipart upload with a network error during part upload."""
    upload_id = "cafe"
    post_response, post_response_context = mock_s3_response_factory(status_code=200)
    post_response.read.return_value = f"""<?xml version="1.0" encoding="UTF-8"?>
    <InitiateMultipartUploadResult>
       <Bucket>{mock_config_entry.data[CONF_BUCKET]}</Bucket>
       <Key>{mock_agent_backup_object_key}</Key>
       <UploadId>{upload_id}</UploadId>
    </InitiateMultipartUploadResult>
    """.encode()
    mock_s3_client.post.return_value = post_response_context

    mock_s3_client.put.side_effect = ClientConnectionError()

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_MIN_SIZE",
            new=0,
        ),
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_PART_SIZE",
            new=512,
        ),
    ):
        await _upload_backup(
            hass_client=hass_client,
            agent_id=agent_id,
            agent_backup=mock_agent_backup,
        )

    await hass.async_block_till_done()

    assert f"Upload failed for {agent_id}: Failed to connect" in caplog.text


async def test_multipart_upload_creation_server_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    agent_id: str,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test multipart upload with a server error during upload creation."""
    _, post_response_context = mock_s3_response_factory(status_code=500)
    mock_s3_client.post.return_value = post_response_context

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_MIN_SIZE",
            new=0,
        ),
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_PART_SIZE",
            new=512,
        ),
    ):
        await _upload_backup(
            hass_client=hass_client,
            agent_id=agent_id,
            agent_backup=mock_agent_backup,
        )

    await hass.async_block_till_done()

    assert (
        f"Upload failed for {agent_id}: Scaleway service is temporarily unavailable"
        in caplog.text
    )


async def test_multipart_upload_part_upload_server_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    agent_id: str,
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
    mock_agent_backup_object_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test multipart upload with a server error during part upload."""
    upload_id = "cafe"
    post_response, post_response_context = mock_s3_response_factory(status_code=200)
    post_response.read.return_value = f"""<?xml version="1.0" encoding="UTF-8"?>
    <InitiateMultipartUploadResult>
       <Bucket>{mock_config_entry.data[CONF_BUCKET]}</Bucket>
       <Key>{mock_agent_backup_object_key}</Key>
       <UploadId>{upload_id}</UploadId>
    </InitiateMultipartUploadResult>
    """.encode()
    mock_s3_client.post.return_value = post_response_context

    _, put_response_context = mock_s3_response_factory(status_code=500)
    mock_s3_client.put.return_value = put_response_context

    with (
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_MIN_SIZE",
            new=0,
        ),
        patch(
            "homeassistant.components.scaleway_object_storage.backup.MULTIPART_PART_SIZE",
            new=512,
        ),
    ):
        await _upload_backup(
            hass_client=hass_client,
            agent_id=agent_id,
            agent_backup=mock_agent_backup,
        )

    await hass.async_block_till_done()

    assert (
        f"Upload failed for {agent_id}: Scaleway service is temporarily unavailable"
        in caplog.text
    )
