"""Tests for the Bond fan device."""
from datetime import timedelta

from bond import BOND_DEVICE_TYPE_CEILING_FAN

from homeassistant import core
from homeassistant.components import fan
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from ...common import async_fire_time_changed
from .common import setup_platform

from tests.async_mock import patch


def ceiling_fan(name: str):
    """Create a ceiling fan with given name."""
    return {
        "name": name,
        "type": BOND_DEVICE_TYPE_CEILING_FAN,
        "actions": ["SetSpeed"],
    }


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()
    assert [key for key in registry.entities.keys()] == ["fan.name_1"]


async def test_turn_on_fan(hass: core.HomeAssistant):
    """Tests that turn on command delegates to API."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch("homeassistant.components.bond.Bond.turnOn") as mock_turn_on, patch(
        "homeassistant.components.bond.Bond.setSpeed"
    ) as mock_set_speed:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "fan.name_1", fan.ATTR_SPEED: fan.SPEED_LOW},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_set_speed.assert_called_once()
        mock_turn_on.assert_called_once()


async def test_turn_off_fan(hass: core.HomeAssistant):
    """Tests that turn off command delegates to API."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch("homeassistant.components.bond.Bond.turnOff") as mock_turn_off:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "fan.name_1"}, blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_off.assert_called_once()


async def test_update_reports_fan_on(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports fan power is on."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState",
        return_value={"power": 1, "speed": 1},
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == "on"


async def test_update_reports_fan_off(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports fan power is off."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState",
        return_value={"power": 0, "speed": 1},
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == "off"
