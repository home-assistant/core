"""The switch tests for the Airzone Cloud platform."""

from unittest.mock import patch

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

    state = hass.states.get("switch.dormitorio")
    assert state.state == STATE_OFF

    state = hass.states.get("switch.salon")
    assert state.state == STATE_ON


async def test_airzone_switch_off(hass: HomeAssistant) -> None:
    """Test switch off."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: "switch.salon",
            },
            blocking=True,
        )

    state = hass.states.get("switch.salon")
    assert state.state == STATE_OFF


async def test_airzone_switch_on(hass: HomeAssistant) -> None:
    """Test switch on."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "switch.dormitorio",
            },
            blocking=True,
        )

    state = hass.states.get("switch.dormitorio")
    assert state.state == STATE_ON
