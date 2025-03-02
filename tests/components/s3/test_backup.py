"""Test the S3 backup platform."""

from collections.abc import AsyncGenerator
from io import StringIO
import json
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.s3.backup import (
    _deserialize,
    _get_key,
    _serialize,
    async_register_backup_agents_listener,
)
from homeassistant.components.s3.const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import TEST_BACKUP

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
        async_initialize_backup(hass)
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
        await setup_integration(hass, mock_config_entry)

        await hass.async_block_till_done()
        yield


async def test_get_key() -> None:
    """Test the _get_key function."""
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
    expected_key = "a1b2c3_my_pretty_backup_2021-01-01_01.02_03000000.tar"
    assert _get_key(backup) == expected_key


async def test_serialize() -> None:
    """Test the _serialize function."""
    metadata = {
        "key1": "value1",
        "key2": 123,
        "key3": {"nested_key": 'nested "value'},
        "key4": "666",
    }

    expected_output = {
        "key1": '"value1"',
        "key2": "123",
        "key3": '{"nested_key": "nested \\"value"}',
        "key4": '"666"',
    }

    assert _serialize(metadata) == expected_output


async def test_serialize_empty() -> None:
    """Test the _serialize function with empty metadata."""
    metadata = {}
    expected_output = {}

    assert _serialize(metadata) == expected_output


async def test_deserialize() -> None:
    """Test the _deserialize function."""
    metadata = {
        "key1": '"value1"',
        "key2": "123",
        "key3": '{"nested_key": "nested \\"value"}',
        "key4": '"666"',
    }

    expected_output = {
        "key1": "value1",
        "key2": 123,
        "key3": {"nested_key": 'nested "value'},
        "key4": "666",
    }

    assert _deserialize(metadata) == expected_output


async def test_deserialize_empty() -> None:
    """Test the _deserialize function with empty metadata."""
    metadata = {}
    expected_output = {}

    assert _deserialize(metadata) == expected_output


async def test_deserialize_invalid_json() -> None:
    """Test the _deserialize function with invalid JSON."""
    metadata = {
        "key1": "{invalid_json",
    }

    with pytest.raises(json.JSONDecodeError):
        _deserialize(metadata)


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
) -> None:
    """Test agent list backups."""

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": [],
            "agents": {
                f"{DOMAIN}.{mock_config_entry.entry_id}": {
                    "protected": False,
                    "size": 34519040,
                }
            },
            "backup_id": "23e64aec",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "failed_agent_ids": [],
            "extra_metadata": {},
            "with_automatic_settings": None,
        }
    ]


async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test agent get backup."""

    backup_id = TEST_BACKUP.backup_id
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == {
        "addons": [],
        "agents": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": {
                "protected": False,
                "size": 34519040,
            }
        },
        "backup_id": "23e64aec",
        "date": "2024-11-22T11:48:48.727189+01:00",
        "database_included": True,
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2024.12.0.dev0",
        "extra_metadata": {},
        "name": "Core 2024.12.0.dev0",
        "failed_agent_ids": [],
        "with_automatic_settings": None,
    }


async def test_agents_get_backup_does_not_throw_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
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
    mock_client.delete_object.assert_called_once()


async def test_agents_delete_not_throwing_on_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Test agent delete backup does not throw on a backup not found."""
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
) -> None:
    """Test agent upload backup."""
    client = await hass_client()
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        ) as fetch_backup,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=AgentBackup(
                addons=[],
                backup_id="23e64aec",
                date="2024-11-22T11:48:48.727189+01:00",
                database_included=True,
                extra_metadata={},
                folders=[],
                homeassistant_included=True,
                homeassistant_version="2024.12.0.dev0",
                name="Core 2024.12.0.dev0",
                protected=False,
                size=34519040,
            ),
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[b"test", b""])
        fetch_backup.return_value = AgentBackup(
            addons=[],
            backup_id="23e64aec",
            date="2024-11-22T11:48:48.727189+01:00",
            database_included=True,
            extra_metadata={},
            folders=[],
            homeassistant_included=True,
            homeassistant_version="2024.12.0.dev0",
            name="Core 2024.12.0.dev0",
            protected=False,
            size=34519040,
        )
        resp = await client.post(
            f"/api/backup/upload?agent_id={DOMAIN}.{mock_config_entry.entry_id}",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert "Uploading backup 23e64aec" in caplog.text
    mock_client.create_multipart_upload.assert_awaited_once()
    mock_client.upload_part.assert_awaited()
    mock_client.complete_multipart_upload.assert_awaited_once()


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
    mock_client.get_object.assert_called_once()


async def test_error_during_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the error wrapper."""
    mock_client.delete_object.side_effect = Exception("Failed to delete backup")

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "backup/delete",
            "backup_id": TEST_BACKUP.backup_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agent_errors": {
            f"{DOMAIN}.{mock_config_entry.entry_id}": "Failed to delete backup"
        }
    }


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [
        listener
    ]  # make sure it's the last listener
    remove_listener()

    assert hass.data.get(DATA_BACKUP_AGENT_LISTENERS) == []
