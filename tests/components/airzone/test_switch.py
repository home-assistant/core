"""The switch tests for the Airzone platform."""

from unittest.mock import patch

from aioairzone.const import (
    API_ANTI_FREEZE,
    API_DATA,
    API_ON,
    API_SYSTEM_ID,
    API_ZONE_ID,
)

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import STATE_OFF, STATE_ON, CommonServiceArgument
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


async def test_airzone_create_anti_freeze_switches(hass: HomeAssistant) -> None:
    """Test creation of anti-freeze switches."""

    await async_init_integration(hass)

    assert hass.states.get("switch.salon_anti_freeze") is None

    state = hass.states.get("switch.dorm_1_anti_freeze")
    assert state.state == STATE_ON

    state = hass.states.get("switch.dorm_2_anti_freeze")
    assert state.state == STATE_OFF


async def test_airzone_anti_freeze_switch_off(hass: HomeAssistant) -> None:
    """Test anti-freeze switch off."""

    await async_init_integration(hass)

    put_hvac_off = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 3,
                API_ANTI_FREEZE: False,
            }
        ]
    }

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=put_hvac_off,
    ) as mock_put:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.dorm_1_anti_freeze"},
            blocking=True,
        )

    mock_put.assert_called_once_with(
        {API_SYSTEM_ID: 1, API_ZONE_ID: 3, API_ANTI_FREEZE: False}
    )
    state = hass.states.get("switch.dorm_1_anti_freeze")
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
            SwitchService.TURN_OFF,
            {
                CommonServiceArgument.ENTITY_ID: "switch.dorm_1",
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
            SwitchService.TURN_ON,
            {
                CommonServiceArgument.ENTITY_ID: "switch.dorm_2",
            },
            blocking=True,
        )

    state = hass.states.get("switch.dorm_2")
    assert state.state == STATE_ON
