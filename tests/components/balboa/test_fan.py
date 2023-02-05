"""Tests of the fan entity of the balboa integration."""
from __future__ import annotations

from unittest.mock import MagicMock

from pybalboa.enums import OffLowHighState, OffOnState

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    FanEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_FAN = "fan.fakespa_"


async def test_pump_with_speeds(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test pump with multiple speeds."""
    fan = f"{ENTITY_FAN}pump_{1}"
    state = hass.states.get(fan)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "FakeSpa Pump 1"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == FanEntityFeature.SET_SPEED
    assert state.attributes[ATTR_PERCENTAGE] == 0
    assert state.attributes[ATTR_PERCENTAGE_STEP] == 50

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: fan, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    pump = client.pumps[0]
    pump.state = OffLowHighState.LOW
    pump.emit("")
    await hass.async_block_till_done()
    pump.set_state.assert_called_once()
    state = hass.states.get(fan)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50


async def test_pump_without_speeds(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test pump without multiple speeds."""
    fan = f"{ENTITY_FAN}pump_{2}"
    state = hass.states.get(fan)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "FakeSpa Pump 2"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes.get(ATTR_PERCENTAGE) is None
    assert state.attributes.get(ATTR_PERCENTAGE_STEP) is None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan},
        blocking=True,
    )
    pump = client.pumps[1]
    pump.state = OffOnState.ON
    pump.emit("")
    await hass.async_block_till_done()
    pump.set_state.assert_called_once()
    state = hass.states.get(fan)
    assert state.state == STATE_ON

    pump.set_state.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: fan},
        blocking=True,
    )
    pump.state = OffOnState.OFF
    pump.emit("")
    await hass.async_block_till_done()
    pump.set_state.assert_called_once()
    state = hass.states.get(fan)
    assert state.state == STATE_OFF
