"""Test the Litter-Robot switch entity."""

from unittest.mock import MagicMock

from pylitterbot import FeederRobot, Robot
import pytest

from homeassistant.components.litterrobot import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .conftest import setup_integration

NIGHT_LIGHT_MODE_ENTITY_ID = "switch.test_night_light_mode"
PANEL_LOCKOUT_ENTITY_ID = "switch.test_panel_lockout"


async def test_switch(
    hass: HomeAssistant, mock_account: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Tests the switch entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    state = hass.states.get(NIGHT_LIGHT_MODE_ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    entity_entry = entity_registry.async_get(NIGHT_LIGHT_MODE_ENTITY_ID)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG


@pytest.mark.parametrize(
    ("entity_id", "robot_command", "updated_field"),
    [
        (NIGHT_LIGHT_MODE_ENTITY_ID, "set_night_light", "nightLightActive"),
        (PANEL_LOCKOUT_ENTITY_ID, "set_panel_lockout", "panelLockActive"),
    ],
)
async def test_on_off_commands(
    hass: HomeAssistant,
    mock_account: MagicMock,
    entity_id: str,
    robot_command: str,
    updated_field: str,
) -> None:
    """Test sending commands to the switch."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)
    robot: Robot = mock_account.robots[0]

    state = hass.states.get(entity_id)
    assert state

    data = {ATTR_ENTITY_ID: entity_id}

    services = ((SERVICE_TURN_ON, STATE_ON, "1"), (SERVICE_TURN_OFF, STATE_OFF, "0"))
    for count, (service, new_state, new_value) in enumerate(services):
        await hass.services.async_call(PLATFORM_DOMAIN, service, data, blocking=True)
        robot._update_data({updated_field: new_value}, partial=True)

        assert getattr(robot, robot_command).call_count == count + 1
        assert (state := hass.states.get(entity_id))
        assert state.state == new_state


async def test_feeder_robot_switch(
    hass: HomeAssistant, mock_account_with_feederrobot: MagicMock
) -> None:
    """Tests Feeder-Robot switches."""
    await setup_integration(hass, mock_account_with_feederrobot, PLATFORM_DOMAIN)
    robot: FeederRobot = mock_account_with_feederrobot.robots[0]

    gravity_mode_switch = "switch.test_gravity_mode"

    switch = hass.states.get(gravity_mode_switch)
    assert switch.state == STATE_OFF

    data = {ATTR_ENTITY_ID: gravity_mode_switch}

    services = ((SERVICE_TURN_ON, STATE_ON, True), (SERVICE_TURN_OFF, STATE_OFF, False))
    for count, (service, new_state, new_value) in enumerate(services):
        await hass.services.async_call(PLATFORM_DOMAIN, service, data, blocking=True)
        robot._update_data({"state": {"info": {"gravity": new_value}}}, partial=True)

        assert robot.set_gravity_mode.call_count == count + 1
        assert (state := hass.states.get(gravity_mode_switch))
        assert state.state == new_state


@pytest.mark.parametrize(
    ("preexisting_entity", "disabled_by", "expected_entity", "expected_issue"),
    [
        (True, None, True, True),
        (True, er.RegistryEntryDisabler.USER, False, False),
        (False, None, False, False),
    ],
)
async def test_litterrobot_4_deprecated_switch(
    hass: HomeAssistant,
    mock_account_with_litterrobot_4: MagicMock,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    preexisting_entity: bool,
    disabled_by: er.RegistryEntryDisabler,
    expected_entity: bool,
    expected_issue: bool,
) -> None:
    """Test switch deprecation issue."""
    entity_uid = "LR4C010001-night_light_mode_enabled"
    if preexisting_entity:
        suggested_id = NIGHT_LIGHT_MODE_ENTITY_ID.replace(f"{PLATFORM_DOMAIN}.", "")
        entity_registry.async_get_or_create(
            PLATFORM_DOMAIN,
            DOMAIN,
            entity_uid,
            suggested_object_id=suggested_id,
            disabled_by=disabled_by,
        )

    await setup_integration(hass, mock_account_with_litterrobot_4, PLATFORM_DOMAIN)

    assert (
        entity_registry.async_get(NIGHT_LIGHT_MODE_ENTITY_ID) is not None
    ) is expected_entity
    assert (
        issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_entity_{entity_uid}",
        )
        is not None
    ) is expected_issue
