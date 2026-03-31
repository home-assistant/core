"""Tests for the UniFi Access number platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from unifi_access_api import ApiNotFoundError, DoorLockRuleType

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_INTERVAL_UNIQUE_ID = "door-001-lock_rule_interval"
BACK_DOOR_INTERVAL_UNIQUE_ID = "door-002-lock_rule_interval"
FRONT_DOOR_LOCK_RULE_SELECT_UNIQUE_ID = "door-001-lock_rule_select"


def _number_entity_id(entity_registry: er.EntityRegistry, unique_id: str) -> str:
    """Return the entity ID for a number entity."""
    entity_id = entity_registry.async_get_entity_id("number", "unifi_access", unique_id)
    assert entity_id is not None
    return entity_id


def _select_entity_id(entity_registry: er.EntityRegistry, unique_id: str) -> str:
    """Return the entity ID for a select entity."""
    entity_id = entity_registry.async_get_entity_id("select", "unifi_access", unique_id)
    assert entity_id is not None
    return entity_id


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
        for entity_id in (
            _number_entity_id(entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID),
            _number_entity_id(entity_registry, BACK_DOOR_INTERVAL_UNIQUE_ID),
        ):
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
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)
        entity_registry.async_update_entity(
            _number_entity_id(entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID),
            disabled_by=None,
        )
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(
        _number_entity_id(entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID)
    )
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
        entity_registry.async_update_entity(
            _number_entity_id(entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID),
            disabled_by=None,
        )
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    await hass.services.async_call(
        Platform.NUMBER,
        "set_value",
        {
            "entity_id": _number_entity_id(
                entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID
            ),
            "value": 30,
        },
        blocking=True,
    )

    assert coordinator.lock_rule_intervals.get("door-001") == 30


async def test_number_value_is_used_when_applying_lock_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the configured interval is used when applying a lock rule."""
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS",
        [Platform.NUMBER, Platform.SELECT],
    ):
        await setup_integration(hass, mock_config_entry)
        entity_registry.async_update_entity(
            _number_entity_id(entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID),
            disabled_by=None,
        )
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        Platform.NUMBER,
        "set_value",
        {
            "entity_id": _number_entity_id(
                entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID
            ),
            "value": 30,
        },
        blocking=True,
    )
    await hass.services.async_call(
        Platform.SELECT,
        "select_option",
        {
            "entity_id": _select_entity_id(
                entity_registry, FRONT_DOOR_LOCK_RULE_SELECT_UNIQUE_ID
            ),
            "option": "keep_lock",
        },
        blocking=True,
    )

    call = mock_client.set_door_lock_rule.call_args
    assert call is not None
    assert call.args[0] == "door-001"
    assert call.args[1].type == DoorLockRuleType.KEEP_LOCK
    assert call.args[1].interval == 30


async def test_number_not_created_when_lock_rules_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that number entities are not created when lock rules are unsupported."""
    mock_client.get_door_lock_rule.side_effect = ApiNotFoundError()
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    assert (
        entity_registry.async_get_entity_id(
            "number", "unifi_access", FRONT_DOOR_INTERVAL_UNIQUE_ID
        )
        is None
    )


async def test_number_restores_last_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number restores its last normalized value after reload."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)
        entity_registry.async_update_entity(
            _number_entity_id(entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID),
            disabled_by=None,
        )
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            Platform.NUMBER,
            "set_value",
            {
                "entity_id": _number_entity_id(
                    entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID
                ),
                "value": 30.9,
            },
            blocking=True,
        )

        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(
        _number_entity_id(entity_registry, FRONT_DOOR_INTERVAL_UNIQUE_ID)
    )
    assert state is not None
    assert float(state.state) == 31.0
    assert mock_config_entry.runtime_data.lock_rule_intervals["door-001"] == 31
