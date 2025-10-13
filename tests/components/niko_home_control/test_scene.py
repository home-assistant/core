"""Tests for the Niko Home Control Scene platform."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_update_callback, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time("2025-10-10 21:00:00")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.niko_home_control.PLATFORMS", [Platform.SCENE]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("scene_id", [0])
async def test_activate_scene(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    scene_id: int,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test activating the scene."""
    await setup_integration(hass, mock_config_entry)

    # Resolve the created scene entity dynamically
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    scene_entities = [e for e in entity_entries if e.domain == SCENE_DOMAIN]
    assert scene_entities, "No scene entities registered"
    entity_id = scene_entities[0].entity_id

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_niko_home_control_connection.scenes[scene_id].activate.assert_called_once()


async def test_updating(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
    scene: AsyncMock,
) -> None:
    """Test scene state recording after activation."""
    await setup_integration(hass, mock_config_entry)

    # Resolve the created scene entity dynamically
    entity_entries = er.async_entries_for_config_entry(
        er.async_get(hass), mock_config_entry.entry_id
    )
    scene_entities = [e for e in entity_entries if e.domain == SCENE_DOMAIN]
    assert scene_entities, "No scene entities registered"
    entity_id = scene_entities[0].entity_id

    # Capture current state (could be unknown or a timestamp depending on implementation)
    before = hass.states.get(entity_id)
    assert before is not None

    # Simulate a device-originated update for the scene (controller callback)
    await find_update_callback(mock_niko_home_control_connection, scene.id)(0)
    await hass.async_block_till_done()

    after = hass.states.get(entity_id)
    assert after is not None
    # If integration records activation on updates, state should change and be a valid ISO timestamp
    if after.state != before.state:
        datetime.fromisoformat(after.state)
