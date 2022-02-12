"""Test the Litter-Robot switch entity."""
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.litterrobot.entity import REFRESH_WAIT_TIME_SECONDS
from homeassistant.components.switch import (
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util.dt import utcnow

from .conftest import setup_integration

from tests.common import async_fire_time_changed

NIGHT_LIGHT_MODE_ENTITY_ID = "switch.test_night_light_mode"
PANEL_LOCKOUT_ENTITY_ID = "switch.test_panel_lockout"


async def test_switch(hass: HomeAssistant, mock_account: MagicMock):
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
    "entity_id,robot_command",
    [
        (NIGHT_LIGHT_MODE_ENTITY_ID, "set_night_light"),
        (PANEL_LOCKOUT_ENTITY_ID, "set_panel_lockout"),
    ],
)
async def test_on_off_commands(
    hass: HomeAssistant, mock_account: MagicMock, entity_id: str, robot_command: str
):
    """Test sending commands to the switch."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    state = hass.states.get(entity_id)
    assert state

    data = {ATTR_ENTITY_ID: entity_id}

    count = 0
    for service in [SERVICE_TURN_ON, SERVICE_TURN_OFF]:
        count += 1

        await hass.services.async_call(
            PLATFORM_DOMAIN,
            service,
            data,
            blocking=True,
        )

        future = utcnow() + timedelta(seconds=REFRESH_WAIT_TIME_SECONDS)
        async_fire_time_changed(hass, future)
        assert getattr(mock_account.robots[0], robot_command).call_count == count
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_ON if service == SERVICE_TURN_ON else STATE_OFF
