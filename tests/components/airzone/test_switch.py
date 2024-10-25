"""The switch tests for the Airzone platform."""

from unittest.mock import patch

from aioairzone.const import API_DATA, API_ON, API_SYSTEM_ID, API_ZONE_ID

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_switches(hass: HomeAssistant) -> None:
    """Test creation of switches."""

    await async_init_integration(hass)

    state = hass.states.get("switch.despacho")
    assert state.state == STATE_OFF

    state = hass.states.get("switch.dorm_1")
    assert state.state == STATE_ON

    state = hass.states.get("switch.dorm_2")
    assert state.state == STATE_OFF

    state = hass.states.get("switch.dorm_ppal")
    assert state.state == STATE_ON

    state = hass.states.get("switch.salon")
    assert state.state == STATE_OFF


async def test_airzone_switch_off(hass: HomeAssistant) -> None:
    """Test switch off."""

    await async_init_integration(hass)

    put_hvac_off = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_ON: False,
            }
        ]
    }

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_off,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: "switch.dorm_1",
            },
            blocking=True,
        )

    state = hass.states.get("switch.dorm_1")
    assert state.state == STATE_OFF


async def test_airzone_switch_on(hass: HomeAssistant) -> None:
    """Test switch on."""

    await async_init_integration(hass)

    put_hvac_on = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 5,
                API_ON: True,
            }
        ]
    }

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_on,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "switch.dorm_2",
            },
            blocking=True,
        )

    state = hass.states.get("switch.dorm_2")
    assert state.state == STATE_ON
