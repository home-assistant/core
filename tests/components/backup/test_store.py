"""Tests for the Backup integration."""

from typing import Any

from syrupy import SnapshotAssertion

from homeassistant.components.backup.const import DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_backup_integration


async def test_store_migration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test migrating the backup store."""
    hass_storage[DOMAIN] = {
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
    }
    await setup_backup_integration(hass)
    await hass.async_block_till_done()

    assert hass_storage[DOMAIN] == snapshot
