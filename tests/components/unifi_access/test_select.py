"""Tests for the UniFi Access select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from unifi_access_api import ApiNotFoundError, DoorLockRuleStatus, DoorLockRuleType

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_LOCK_RULE_SELECT_ENTITY = "select.front_door_door_lock_rule"
BACK_DOOR_LOCK_RULE_SELECT_ENTITY = "select.back_door_door_lock_rule"


async def test_select_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select entities are created with expected state."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(
            type=DoorLockRuleType.KEEP_LOCK, ended_time=1700000000
        )
    )
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_current_option_no_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test select reflects unknown state when no lock rule is active."""
    mock_client.get_door_lock_rule = AsyncMock(return_value=DoorLockRuleStatus())
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_select_current_option_active_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test select reflects the current lock rule type."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(type=DoorLockRuleType.KEEP_LOCK)
    )
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "keep_lock"


async def test_select_option_calls_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test selecting an option calls set_door_lock_rule on the client."""
    mock_client.get_door_lock_rule = AsyncMock(return_value=DoorLockRuleStatus())
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]
    ):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        Platform.SELECT,
        "select_option",
        {"entity_id": FRONT_DOOR_LOCK_RULE_SELECT_ENTITY, "option": "keep_lock"},
        blocking=True,
    )

    mock_client.set_door_lock_rule.assert_called_once()
    call_args = mock_client.set_door_lock_rule.call_args
    assert call_args[0][0] == "door-001"
    assert call_args[0][1].type == DoorLockRuleType.KEEP_LOCK


async def test_select_not_created_when_lock_rules_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that select entities are not created when lock rules are unsupported."""
    mock_client.get_door_lock_rule = AsyncMock(side_effect=ApiNotFoundError)
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY) is None


async def test_select_lock_early_option_shown_for_schedule_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test lock_early appears in options when a schedule rule is active."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(type=DoorLockRuleType.SCHEDULE)
    )
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY)
    assert state is not None
    assert "lock_early" in state.attributes["options"]


async def test_select_lock_early_option_hidden_for_non_schedule_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test lock_early is absent from options when no schedule rule is active."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(type=DoorLockRuleType.KEEP_LOCK)
    )
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY)
    assert state is not None
    assert "lock_early" not in state.attributes["options"]
