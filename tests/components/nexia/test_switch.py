"""The switch tests for the nexia platform."""

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_hold_switch(hass: HomeAssistant) -> None:
    """Test creation of the hold switch."""
    await async_init_integration(hass)
    assert hass.states.get("switch.nick_office_hold").state == STATE_ON


async def test_log_response_switch(hass: HomeAssistant) -> None:
    """Test log response switch."""
    await async_init_integration(hass)
    test_entity = f"{Platform.SWITCH}.log_responses"

    # The switch starts out off.
    assert (entity_state := hass.states.get(test_entity)) is not None
    assert entity_state.state == STATE_OFF

    # Turn switch on.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    assert hass.states.get(test_entity).state == STATE_ON

    # Turn switch back off.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    assert hass.states.get(test_entity).state == STATE_OFF
