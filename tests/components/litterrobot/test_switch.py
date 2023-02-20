"""Test the Litter-Robot switch entity."""
from unittest.mock import MagicMock

from pylitterbot import Robot
import pytest

from homeassistant.components.switch import (
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .conftest import setup_integration

NIGHT_LIGHT_MODE_ENTITY_ID = "switch.test_night_light_mode"
PANEL_LOCKOUT_ENTITY_ID = "switch.test_panel_lockout"


async def test_switch(hass: HomeAssistant, mock_account: MagicMock) -> None:
    """Tests the switch entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    state = hass.states.get(NIGHT_LIGHT_MODE_ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    ent_reg = entity_registry.async_get(hass)
    entity_entry = ent_reg.async_get(NIGHT_LIGHT_MODE_ENTITY_ID)
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

    count = 0
    services = ((SERVICE_TURN_ON, STATE_ON, "1"), (SERVICE_TURN_OFF, STATE_OFF, "0"))
    for service, new_state, new_value in services:
        count += 1
        await hass.services.async_call(PLATFORM_DOMAIN, service, data, blocking=True)
        robot._update_data({updated_field: new_value}, partial=True)

        assert getattr(robot, robot_command).call_count == count
        assert (state := hass.states.get(entity_id))
        assert state.state == new_state
