"""Tests for the Backup integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup.const import DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_backup_integration

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def mock_delay_save() -> Generator[None]:
    """Mock the delay save constant."""
    with patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0):
        yield


@pytest.mark.parametrize(
    "store_data",
    [
        {
            "data": {
                "backups": [
                    {
                        "backup_id": "abc123",
                        "failed_agent_ids": ["test.remote"],
                    }
                ],
                "config": {
                    "create_backup": {
                        "agent_ids": [],
                        "include_addons": None,
                        "include_all_addons": False,
                        "include_database": True,
                        "include_folders": None,
                        "name": None,
                        "password": None,
                    },
                    "last_attempted_automatic_backup": None,
                    "last_completed_automatic_backup": None,
                    "retention": {
                        "copies": None,
                        "days": None,
                    },
                    "schedule": {
                        "state": "never",
                    },
                },
            },
            "key": DOMAIN,
            "version": 1,
        },
        {
            "data": {
                "backups": [
                    {
                        "backup_id": "abc123",
                        "failed_agent_ids": ["test.remote"],
                    }
                ],
                "config": {
                    "create_backup": {
                        "agent_ids": [],
                        "include_addons": None,
                        "include_all_addons": False,
                        "include_database": True,
                        "include_folders": None,
                        "name": None,
                        "password": None,
                    },
                    "last_attempted_automatic_backup": None,
                    "last_completed_automatic_backup": None,
                    "retention": {
                        "copies": 0,
                        "days": 0,
                    },
                    "schedule": {
                        "state": "never",
                    },
                },
            },
            "key": DOMAIN,
            "version": 1,
        },
        {
            "data": {
                "backups": [
                    {
                        "backup_id": "abc123",
                        "failed_agent_ids": ["test.remote"],
                    }
                ],
                "config": {
                    "agents": {"test.remote": {"protected": True}},
                    "automatic_backups_configured": False,
                    "create_backup": {
                        "agent_ids": [],
                        "include_addons": None,
                        "include_all_addons": False,
                        "include_database": True,
                        "include_folders": None,
                        "name": None,
                        "password": None,
                    },
                    "last_attempted_automatic_backup": None,
                    "last_completed_automatic_backup": None,
                    "retention": {
                        "copies": None,
                        "days": None,
                    },
                    "schedule": {
                        "days": [],
                        "recurrence": "never",
                        "time": None,
                    },
                    "something_from_the_future": "value",
                },
            },
            "key": DOMAIN,
            "version": 2,
        },
        {
            "data": {
                "backups": [
                    {
                        "backup_id": "abc123",
                        "failed_agent_ids": ["test.remote"],
                    }
                ],
                "config": {
                    "agents": {"test.remote": {"protected": True}},
                    "create_backup": {
                        "agent_ids": [],
                        "include_addons": None,
                        "include_all_addons": False,
                        "include_database": True,
                        "include_folders": None,
                        "name": None,
                        "password": None,
                    },
                    "last_attempted_automatic_backup": None,
                    "last_completed_automatic_backup": None,
                    "retention": {
                        "copies": None,
                        "days": None,
                    },
                    "schedule": {
                        "days": [],
                        "recurrence": "never",
                        "state": "never",
                        "time": None,
                    },
                },
            },
            "key": DOMAIN,
            "minor_version": 4,
            "version": 1,
        },
        {
            "data": {
                "backups": [
                    {
                        "backup_id": "abc123",
                        "failed_agent_ids": ["test.remote"],
                    }
                ],
                "config": {
                    "agents": {"test.remote": {"protected": True}},
                    "create_backup": {
                        "agent_ids": [],
                        "include_addons": None,
                        "include_all_addons": False,
                        "include_database": True,
                        "include_folders": None,
                        "name": None,
                        "password": "hunter2",
                    },
                    "last_attempted_automatic_backup": None,
                    "last_completed_automatic_backup": None,
                    "retention": {
                        "copies": None,
                        "days": None,
                    },
                    "schedule": {
                        "days": [],
                        "recurrence": "never",
                        "state": "never",
                        "time": None,
                    },
                },
            },
            "key": DOMAIN,
            "minor_version": 4,
            "version": 1,
        },
    ],
)
async def test_store_migration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    store_data: dict[str, Any],
) -> None:
    """Test migrating the backup store."""
    hass_storage[DOMAIN] = store_data
    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    # Check migrated data
    assert hass_storage[DOMAIN] == snapshot

    # Update settings, then check saved data
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "backup/config/update",
            "create_backup": {"agent_ids": ["test-agent"]},
        }
    )
    result = await client.receive_json()
    assert result["success"]
    await hass.async_block_till_done()
    assert hass_storage[DOMAIN] == snapshot
