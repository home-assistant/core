"""Tests for the sensors of the Backup integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup import store
from homeassistant.components.backup.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_backup_integration

from tests.common import async_fire_time_changed, snapshot_platform
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("mock_backup_generation")
async def test_sensors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of backup sensors."""
    with patch("homeassistant.components.backup.PLATFORMS", [Platform.SENSOR]):
        await setup_backup_integration(hass, with_hassio=False)
        await hass.async_block_till_done(wait_background_tasks=True)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    # start backup and check sensor states again
    client = await hass_ws_client(hass)
    await hass.async_block_till_done()
    await client.send_json_auto_id(
        {"type": "backup/generate", "agent_ids": ["backup.local"]}
    )

    assert await client.receive_json()
    state = hass.states.get("sensor.backup_backup_manager_state")
    assert state.state == "create_backup"

    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("sensor.backup_backup_manager_state")
    assert state.state == "idle"


async def test_sensor_updates(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
    create_backup: AsyncMock,
) -> None:
    """Test update of backup sensors."""
    # Ensure created backup is already protected,
    # to avoid manager creating a new EncryptedBackupStreamer
    # instead of using the already mocked stream writer.
    created_backup: MagicMock = create_backup.return_value[1].result().backup
    created_backup.protected = True

    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2024-11-12T12:00:00+01:00")
    storage_data = {
        "backups": [],
        "config": {
            "agents": {},
            "automatic_backups_configured": True,
            "create_backup": {
                "agent_ids": ["test.remote"],
                "include_addons": [],
                "include_all_addons": False,
                "include_database": True,
                "include_folders": [],
                "name": "test-name",
                "password": "test-password",
            },
            "retention": {"copies": None, "days": None},
            "last_attempted_automatic_backup": "2024-11-11T04:45:00+01:00",
            "last_completed_automatic_backup": "2024-11-11T04:45:00+01:00",
            "schedule": {
                "days": [],
                "recurrence": "daily",
                "state": "never",
                "time": "06:00",
            },
        },
    }
    hass_storage[DOMAIN] = {
        "data": storage_data,
        "key": DOMAIN,
        "version": store.STORAGE_VERSION,
        "minor_version": store.STORAGE_VERSION_MINOR,
    }

    with patch("homeassistant.components.backup.PLATFORMS", [Platform.SENSOR]):
        await setup_backup_integration(
            hass, with_hassio=False, remote_agents=["test.remote"]
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.backup_last_attempted_automatic_backup")
    assert state.state == "2024-11-11T03:45:00+00:00"
    state = hass.states.get("sensor.backup_last_successful_automatic_backup")
    assert state.state == "2024-11-11T03:45:00+00:00"
    state = hass.states.get("sensor.backup_next_scheduled_automatic_backup")
    assert state.state == "2024-11-13T05:00:00+00:00"

    freezer.move_to("2024-11-13T12:00:00+01:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.backup_last_attempted_automatic_backup")
    assert state.state == "2024-11-13T11:00:00+00:00"
    state = hass.states.get("sensor.backup_last_successful_automatic_backup")
    assert state.state == "2024-11-13T11:00:00+00:00"
    state = hass.states.get("sensor.backup_next_scheduled_automatic_backup")
    assert state.state == "2024-11-14T05:00:00+00:00"
