"""Tests for the Bond light device."""
from datetime import timedelta
import logging

from bond import Actions, DeviceTypes

from homeassistant import core
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from .common import setup_platform

from tests.async_mock import patch
from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


def ceiling_fan(name: str):
    """Create a ceiling fan (that has built-in light) with given name."""
    return {
        "name": name,
        "type": DeviceTypes.CEILING_FAN,
        "actions": [Actions.TOGGLE_LIGHT],
    }


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()
    assert [key for key in registry.entities.keys()] == ["light.name_1"]


async def test_turn_on_light(hass: core.HomeAssistant):
    """Tests that turn on command delegates to API."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    with patch("homeassistant.components.bond.Bond.turnLightOn") as mock_turn_light_on:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_light_on.assert_called_once()


async def test_turn_off_light(hass: core.HomeAssistant):
    """Tests that turn off command delegates to API."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.turnLightOff"
    ) as mock_turn_light_off:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_light_off.assert_called_once()


async def test_update_reports_light_is_on(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports the light is on."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState", return_value={"light": 1}
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1").state == "on"


async def test_update_reports_light_is_off(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports the light is off."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState", return_value={"light": 0}
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1").state == "off"
