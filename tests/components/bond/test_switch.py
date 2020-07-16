"""Tests for the Bond switch device."""
from datetime import timedelta
import logging

from bond import DeviceTypes

from homeassistant import core
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from .common import (
    patch_bond_device_state,
    patch_bond_turn_off,
    patch_bond_turn_on,
    setup_platform,
)

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


def generic_device(name: str):
    """Create a generic device with given name."""
    return {"name": name, "type": DeviceTypes.GENERIC_DEVICE}


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()
    assert [key for key in registry.entities] == ["switch.name_1"]


async def test_turn_on_switch(hass: core.HomeAssistant):
    """Tests that turn on command delegates to API."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    with patch_bond_turn_on() as mock_turn_on, patch_bond_device_state():
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_on.assert_called_once()


async def test_turn_off_switch(hass: core.HomeAssistant):
    """Tests that turn off command delegates to API."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    with patch_bond_turn_off() as mock_turn_off, patch_bond_device_state():
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_off.assert_called_once()


async def test_update_reports_switch_is_on(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports the device is on."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    with patch_bond_device_state(return_value={"power": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("switch.name_1").state == "on"


async def test_update_reports_switch_is_off(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports the device is off."""
    await setup_platform(hass, SWITCH_DOMAIN, generic_device("name-1"))

    with patch_bond_device_state(return_value={"power": 0}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("switch.name_1").state == "off"
