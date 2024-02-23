"""Tests of the pump fan entity of the balboa integration."""
from __future__ import annotations

from unittest.mock import MagicMock

from pybalboa.enums import OffLowHighState

from homeassistant.components.fan import ATTR_PERCENTAGE
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.fan import common

ENTITY_FAN = "fan.fakepa_pump_1"


async def test_pump(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test spa filters."""
    pump = MagicMock()

    async def set_state(state: OffLowHighState):
        pump.state = state

    pump.client = client
    pump.index = 0
    pump.state = OffLowHighState.OFF
    pump.set_state = set_state
    pump.options = list(OffLowHighState)
    client.pumps.append(pump)

    state = hass.states.get(ENTITY_FAN)
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, ENTITY_FAN)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100

    await common.async_set_percentage(hass, ENTITY_FAN, 50)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50

    await common.async_turn_off(hass, ENTITY_FAN)
    assert state.state == STATE_OFF
