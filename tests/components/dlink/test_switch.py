"""Switch tests for the D-Link Smart Plug integration."""
from collections.abc import Awaitable, Callable

from homeassistant.components.dlink import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup

from tests.components.repairs import get_repairs


async def test_switch_state(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[None]],
    setup_integration: ComponentSetup,
) -> None:
    """Test we get the switch status."""
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {
                "platform": DOMAIN,
                "host": "1.2.3.4",
                "username": "admin",
                "password": "123456",
                "use_legacy_protocol": True,
            }
        },
    )
    await hass.async_block_till_done()
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "deprecated_yaml"

    await setup_integration()

    entity_id = "switch.mock_title_switch"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes["total_consumption"] == 1040.0
    assert state.attributes["temperature"] == 33
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_switch_no_value(
    hass: HomeAssistant, setup_integration_legacy: ComponentSetup
) -> None:
    """Test we handle 'N/A' being passed by the pypi package."""
    await setup_integration_legacy()

    state = hass.states.get("switch.mock_title_switch")
    assert state.state == STATE_OFF
    assert state.attributes["total_consumption"] is None
    assert state.attributes["temperature"] is None
