"""Tests for the UniFi Access select platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api import (
    ApiConnectionError,
    ApiNotFoundError,
    DoorLockRule,
    DoorLockRuleStatus,
    DoorLockRuleType,
    UnifiAccessError,
)

from homeassistant.components.unifi_access.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_LOCK_RULE_SELECT_ENTITY = "select.front_door_lock_rule"
BACK_DOOR_LOCK_RULE_SELECT_ENTITY = "select.back_door_lock_rule"


@pytest.fixture(autouse=True)
def only_select_platform() -> Generator[None]:
    """Limit setup to the select platform for select tests."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SELECT]):
        yield


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
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_current_option_no_rule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test select reflects unknown state when no lock rule is active."""
    mock_client.get_door_lock_rule = AsyncMock(return_value=DoorLockRuleStatus())
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
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        Platform.SELECT,
        "select_option",
        {"entity_id": FRONT_DOOR_LOCK_RULE_SELECT_ENTITY, "option": "keep_lock"},
        blocking=True,
    )

    mock_client.set_door_lock_rule.assert_awaited_once_with(
        "door-001", DoorLockRule(type=DoorLockRuleType.KEEP_LOCK, interval=10)
    )


async def test_select_schedule_option_does_not_call_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test selecting schedule does not call the API."""
    mock_client.get_door_lock_rule = AsyncMock(
        return_value=DoorLockRuleStatus(type=DoorLockRuleType.SCHEDULE)
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        Platform.SELECT,
        "select_option",
        {"entity_id": FRONT_DOOR_LOCK_RULE_SELECT_ENTITY, "option": "schedule"},
        blocking=True,
    )

    mock_client.set_door_lock_rule.assert_not_awaited()


async def test_select_not_created_when_lock_rules_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that select entities are not created when lock rules are unsupported."""
    mock_client.get_door_lock_rule = AsyncMock(side_effect=ApiNotFoundError())
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
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY)
    assert state is not None
    assert state.state == "schedule"
    assert "schedule" in state.attributes["options"]
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
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY)
    assert state is not None
    assert "lock_early" not in state.attributes["options"]


async def test_select_created_for_supported_doors_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test select entities are created only for doors that support lock rules."""

    async def mock_get_door_lock_rule(door_id: str) -> DoorLockRuleStatus:
        if door_id == "door-001":
            return DoorLockRuleStatus(
                type=DoorLockRuleType.KEEP_LOCK, ended_time=1700000000
            )
        raise ApiNotFoundError

    mock_client.get_door_lock_rule = AsyncMock(side_effect=mock_get_door_lock_rule)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY) is not None
    assert hass.states.get(BACK_DOOR_LOCK_RULE_SELECT_ENTITY) is None


async def test_select_placeholder_created_for_transient_error_doors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test select placeholders are created for doors with transient fetch errors."""

    async def mock_get_door_lock_rule(door_id: str) -> DoorLockRuleStatus:
        if door_id == "door-001":
            raise ApiConnectionError("Connection failed")
        raise ApiNotFoundError

    mock_client.get_door_lock_rule = AsyncMock(side_effect=mock_get_door_lock_rule)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY) is not None
    assert hass.states.get(FRONT_DOOR_LOCK_RULE_SELECT_ENTITY).state == STATE_UNKNOWN
    assert hass.states.get(BACK_DOOR_LOCK_RULE_SELECT_ENTITY) is None


async def test_select_option_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test HomeAssistantError is raised when set_door_lock_rule fails."""
    mock_client.get_door_lock_rule = AsyncMock(return_value=DoorLockRuleStatus())
    await setup_integration(hass, mock_config_entry)

    mock_client.set_door_lock_rule = AsyncMock(
        side_effect=UnifiAccessError("API error")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {
                "entity_id": FRONT_DOOR_LOCK_RULE_SELECT_ENTITY,
                "option": "keep_lock",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "lock_rule_failed"
    assert exc_info.value.translation_domain == DOMAIN
