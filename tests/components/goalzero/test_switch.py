"""Switch tests for the Goalzero integration."""

from homeassistant.components.goalzero.const import DEFAULT_NAME, DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from . import async_init_integration

from tests.common import async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_switches_states(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we get sensor data."""
    await async_init_integration(hass, aioclient_mock)

    assert hass.states.get(f"switch.{DEFAULT_NAME}_usb_port_status").state == STATE_OFF
    assert hass.states.get(f"switch.{DEFAULT_NAME}_ac_port_status").state == STATE_ON
    entity_id = f"switch.{DEFAULT_NAME}_12v_port_status"
    assert hass.states.get(entity_id).state == STATE_OFF
    aioclient_mock.post(
        "http://1.2.3.4/state",
        text=await async_load_fixture(hass, "state_change.json", DOMAIN),
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "http://1.2.3.4/state",
        text=await async_load_fixture(hass, "state_data.json", DOMAIN),
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_OFF
