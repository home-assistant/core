"""The switch tests for the nexia platform."""

from homeassistant.const import STATE_ON

from .util import async_init_integration


async def test_hold_switch(hass):
    """Test creation of the hold switch."""
    await async_init_integration(hass)
    assert hass.states.get("switch.nick_office_hold").state == STATE_ON
