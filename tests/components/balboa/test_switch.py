"""Tests of the switch entity of the balboa integration."""

from __future__ import annotations

from unittest.mock import MagicMock, call

from pybalboa import SpaControl
from pybalboa.enums import LowHighRange, UnknownState
import pytest

from homeassistant.const import STATE_OFF, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import client_update, init_integration

from tests.components.switch import common

ENTITY_SWITCH = "switch.fakespa_temperature_high_range"


@pytest.fixture
def mock_switch(client: MagicMock):
    """Return a mock switch."""
    switch = MagicMock(SpaControl)

    async def set_state(state: LowHighRange):
        switch.state = state

    switch.client = client
    switch.state = LowHighRange.LOW
    switch.set_state = set_state
    client.temperature_range = switch
    return switch


async def test_switch(hass: HomeAssistant, client: MagicMock, mock_switch) -> None:
    """Test spa temperature range switch."""
    await init_integration(hass)

    # check if the initial state is off
    state = hass.states.get(ENTITY_SWITCH)
    assert state.state == STATE_OFF

    # test calling turn on +
    await common.async_turn_on(hass, ENTITY_SWITCH)
    assert client.set_temperature_range.call_count == 1
    assert client.set_temperature_range.call_args == call(LowHighRange.HIGH)

    # test calling turn off
    await common.async_turn_off(hass, ENTITY_SWITCH)
    assert client.set_temperature_range.call_count == 2  # total call count
    assert client.set_temperature_range.call_args == call(LowHighRange.LOW)


async def test_switch_unknown_state(
    hass: HomeAssistant, client: MagicMock, mock_switch
) -> None:
    """Tests spa temperature range switch with unknown state."""
    await init_integration(hass)

    mock_switch.state = UnknownState.UNKNOWN
    state = await client_update(hass, client, ENTITY_SWITCH)
    assert state.state == STATE_UNKNOWN
