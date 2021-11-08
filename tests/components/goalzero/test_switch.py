"""Switch tests for the Goalzero integration."""
from homeassistant.components.goalzero.const import DEFAULT_NAME
from homeassistant.components.switch import DOMAIN as DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from . import async_setup_platform

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_switches_states(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test we get sensor data."""
    aioclient_mock.post(
        "http://1.2.3.4/state",
        text=load_fixture("goalzero/state_data.json"),
    )
    await async_setup_platform(hass, aioclient_mock, DOMAIN)

    entity_id = f"switch.{DEFAULT_NAME}_12v_port_status"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    entity_id = f"switch.{DEFAULT_NAME}_usb_port_status"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    entity_id = f"switch.{DEFAULT_NAME}_ac_port_status"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
