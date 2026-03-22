"""Tests for the UniFi Access number platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from unifi_access_api import ApiNotFoundError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_INTERVAL_ENTITY = "number.front_door_rule_interval_min"
BACK_DOOR_INTERVAL_ENTITY = "number.back_door_rule_interval_min"


async def test_number_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test number entities are created with expected state."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

        # Number entities are disabled by default; enable then reload to get state
        for entity_id in (FRONT_DOOR_INTERVAL_ENTITY, BACK_DOOR_INTERVAL_ENTITY):
            entity_registry.async_update_entity(entity_id, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_number_default_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number entity defaults to 10 minutes when enabled."""
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.NUMBER]
    ):
        await setup_integration(hass, mock_config_entry)
        entity_registry.async_update_entity(FRONT_DOOR_INTERVAL_ENTITY, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_INTERVAL_ENTITY)
    assert state is not None
    assert float(state.state) == 10.0


async def test_number_set_value_syncs_to_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting a value syncs the interval to the coordinator."""
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS",
        [Platform.NUMBER, Platform.SELECT],
    ):
        await setup_integration(hass, mock_config_entry)
        entity_registry.async_update_entity(FRONT_DOOR_INTERVAL_ENTITY, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    await hass.services.async_call(
        Platform.NUMBER,
        "set_value",
        {"entity_id": FRONT_DOOR_INTERVAL_ENTITY, "value": 30},
        blocking=True,
    )

    assert coordinator.lock_rule_intervals.get("door-001") == 30


async def test_number_not_created_when_lock_rules_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that number entities are not created when lock rules are unsupported."""
    mock_client.get_door_lock_rule.side_effect = ApiNotFoundError()
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.NUMBER]
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_INTERVAL_ENTITY) is None


async def test_number_restores_last_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number restores its last value after reload."""
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.NUMBER]
    ):
        await setup_integration(hass, mock_config_entry)
        entity_registry.async_update_entity(FRONT_DOOR_INTERVAL_ENTITY, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            Platform.NUMBER,
            "set_value",
            {"entity_id": FRONT_DOOR_INTERVAL_ENTITY, "value": 30},
            blocking=True,
        )

        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_INTERVAL_ENTITY)
    assert state is not None
    assert float(state.state) == 30.0
    assert mock_config_entry.runtime_data.lock_rule_intervals["door-001"] == 30
