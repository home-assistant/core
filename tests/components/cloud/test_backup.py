"""Test the cloud backup platform."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import Mock, PropertyMock, patch

import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN
from homeassistant.components.cloud import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import MagicMock, WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant, cloud: MagicMock
) -> AsyncGenerator[None]:
    """Set up cloud integration."""
    with patch("homeassistant.components.backup.is_hassio", return_value=False):
        assert await async_setup_component(hass, BACKUP_DOMAIN, {BACKUP_DOMAIN: {}})
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
        yield


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
        "agents": [{"agent_id": "backup.local"}, {"agent_id": "cloud.cloud"}],
        "syncing": False,
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    cloud: MagicMock,
) -> None:
    """Test agent list backups."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.cloud.backup.async_files_list", spec_set=True
    ) as list_files:
        list_files.return_value = [
            {
                "Key": "462e16810d6841228828d9dd2f9e341e.tar",
                "LastModified": "2024-11-22T10:49:01.182Z",
                "Size": 34519040,
                "Metadata": {
                    "addons": [],
                    "backup_id": "23e64aec",
                    "date": "2024-11-22T11:48:48.727189+01:00",
                    "database_included": True,
                    "folders": [],
                    "homeassistant_included": True,
                    "homeassistant_version": "2024.12.0.dev0",
                    "name": "Core 2024.12.0.dev0",
                    "protected": False,
                    "size": 34519040,
                    "storage-type": "backup",
                },
            }
        ]
        await client.send_json_auto_id({"type": "backup/info"})
        response = await client.receive_json()
        list_files.assert_called_once_with(cloud, storage_type="backup")

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backups"] == [
        {
            "addons": [],
            "backup_id": "23e64aec",
            "date": "2024-11-22T11:48:48.727189+01:00",
            "database_included": True,
            "folders": [],
            "homeassistant_included": True,
            "homeassistant_version": "2024.12.0.dev0",
            "name": "Core 2024.12.0.dev0",
            "protected": False,
            "size": 34519040,
            "agent_ids": ["cloud.cloud"],
        }
    ]


@pytest.mark.parametrize(
    ("backup_id", "expected_result"),
    [
        (
            "23e64aec",
            {
                "addons": [],
                "backup_id": "23e64aec",
                "date": "2024-11-22T11:48:48.727189+01:00",
                "database_included": True,
                "folders": [],
                "homeassistant_included": True,
                "homeassistant_version": "2024.12.0.dev0",
                "name": "Core 2024.12.0.dev0",
                "protected": False,
                "size": 34519040,
                "agent_ids": ["cloud.cloud"],
            },
        ),
        (
            "12345",
            None,
        ),
    ],
    ids=["found", "not_found"],
)
async def test_agents_get_backup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    cloud: MagicMock,
    backup_id: str,
    expected_result: dict[str, Any] | None,
    mock_list_files: Mock,
) -> None:
    """Test agent get backup."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "backup/details", "backup_id": backup_id})
    response = await client.receive_json()
    mock_list_files.assert_called_once_with(cloud, storage_type="backup")

    assert response["success"]
    assert response["result"]["agent_errors"] == {}
    assert response["result"]["backup"] == expected_result


async def test_agents_download_not_logged_in(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test agent download backup, when cloud user is logged in."""
    client = await hass_ws_client(hass)
    backup_id = "abc123"

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "agent_id": "cloud.cloud",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "backup_agents_download",
        "message": "Not logged in to cloud",
    }


@pytest.fixture
def mock_list_files() -> Generator[MagicMock]:
    """Mock list files."""
    with patch(
        "homeassistant.components.cloud.backup.async_files_list", spec_set=True
    ) as list_files:
        list_files.return_value = [
            {
                "Key": "462e16810d6841228828d9dd2f9e341e.tar",
                "LastModified": "2024-11-22T10:49:01.182Z",
                "Size": 34519040,
                "Metadata": {
                    "addons": [],
                    "backup_id": "23e64aec",
                    "date": "2024-11-22T11:48:48.727189+01:00",
                    "database_included": True,
                    "folders": [],
                    "homeassistant_included": True,
                    "homeassistant_version": "2024.12.0.dev0",
                    "name": "Core 2024.12.0.dev0",
                    "protected": False,
                    "size": 34519040,
                    "storage-type": "backup",
                },
            }
        ]
        yield list_files


@pytest.fixture
def cloud_logged_in(cloud: MagicMock):
    """Mock cloud logged in."""
    type(cloud).is_logged_in = PropertyMock(return_value=True)


@pytest.mark.usefixtures("cloud_logged_in", "mock_list_files")
async def test_agents_download_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test agent download backup raises error if not found."""
    client = await hass_ws_client(hass)
    backup_id = "1234"

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "agent_id": "cloud.cloud",
            "backup_id": backup_id,
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "backup_agents_download",
        "message": "Backup not found",
    }
