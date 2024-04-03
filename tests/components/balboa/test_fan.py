"""Tests of the pump fan entity of the balboa integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from pybalboa import SpaControl
from pybalboa.enums import OffLowHighState, UnknownState
import pytest

from homeassistant.components.fan import ATTR_PERCENTAGE
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import client_update, init_integration

from tests.components.fan import common

ENTITY_FAN = "fan.fakespa_pump_1"


@pytest.fixture
def mock_pump(client: MagicMock):
    """Return a mock pump."""
    pump = MagicMock(SpaControl)

    async def set_state(state: OffLowHighState):
        pump.state = state

    pump.client = client
    pump.index = 0
    pump.state = OffLowHighState.OFF
    pump.set_state = set_state
    pump.options = list(OffLowHighState)
    client.pumps.append(pump)

    return pump


async def test_pump(hass: HomeAssistant, client: MagicMock, mock_pump) -> None:
    """Test spa pump."""
    await init_integration(hass)

    # check if the initial state is off
    state = hass.states.get(ENTITY_FAN)
    assert state.state == STATE_OFF

    # just call turn on, pump should be at full speed
    await common.async_turn_on(hass, ENTITY_FAN)
    state = await client_update(hass, client, ENTITY_FAN)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100

    # test setting percentage
    await common.async_set_percentage(hass, ENTITY_FAN, 50)
    state = await client_update(hass, client, ENTITY_FAN)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50

    # test calling turn off
    await common.async_turn_off(hass, ENTITY_FAN)
    state = await client_update(hass, client, ENTITY_FAN)
    assert state.state == STATE_OFF

    # test setting percentage to 0
    await common.async_turn_on(hass, ENTITY_FAN)
    await client_update(hass, client, ENTITY_FAN)

    await common.async_set_percentage(hass, ENTITY_FAN, 0)
    state = await client_update(hass, client, ENTITY_FAN)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0


async def test_pump_unknown_state(
    hass: HomeAssistant, client: MagicMock, mock_pump
) -> None:
    """Tests spa pump with unknown state."""
    await init_integration(hass)

    mock_pump.state = UnknownState.UNKNOWN
    state = await client_update(hass, client, ENTITY_FAN)
    assert state.state == STATE_UNKNOWN
