"""Tests for the Telldus Live switch platform."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

SWITCH = "switch.kitchen"


@pytest.mark.parametrize(("is_on", "expected"), [(True, STATE_ON), (False, STATE_OFF)])
@pytest.mark.usefixtures("setup_integration")
async def test_switch_state(
    hass: HomeAssistant, device: MagicMock, is_on: bool, expected: str
) -> None:
    """Test the switch state follows the device."""
    device.is_on = is_on
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH).state == expected


@pytest.mark.parametrize(
    ("service", "method"),
    [(SERVICE_TURN_ON, "turn_on"), (SERVICE_TURN_OFF, "turn_off")],
)
@pytest.mark.usefixtures("setup_integration")
async def test_switch_commands(
    hass: HomeAssistant, device: MagicMock, service: str, method: str
) -> None:
    """Test turning the switch on and off sends the command."""
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: SWITCH}, blocking=True
    )

    getattr(device, method).assert_called_once_with()


@pytest.mark.usefixtures("setup_integration")
async def test_switch_command_rejected(hass: HomeAssistant, device: MagicMock) -> None:
    """Test a rejected command raises."""
    device.turn_on.return_value = False

    with pytest.raises(HomeAssistantError, match="did not accept the command"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SWITCH}, blocking=True
        )
