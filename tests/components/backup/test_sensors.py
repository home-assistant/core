"""Tests for the sensors of the Backup integration."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_backup_integration

from tests.common import snapshot_platform
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("mock_backup_generation")
async def test_sensors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup and update of backup sensors."""
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
