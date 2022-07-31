"""Tests for the Wemo light entity via the bridge."""
from unittest.mock import create_autospec

import pytest
import pywemo

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from . import entity_test_helpers


@pytest.fixture
def pywemo_model():
    """Pywemo Bridge models use the light platform (WemoLight class)."""
    return "Bridge"


# Note: The ordering of where the pywemo_bridge_light comes in test arguments matters.
# In test methods, the pywemo_bridge_light fixture argument must come before the
# wemo_entity fixture argument.
@pytest.fixture(name="pywemo_bridge_light")
def pywemo_bridge_light_fixture(pywemo_device):
    """Fixture for Bridge.Light WeMoDevice instances."""
    light = create_autospec(pywemo.ouimeaux_device.bridge.Light, instance=True)
    light.uniqueID = pywemo_device.serialnumber
    light.name = pywemo_device.name
    light.bridge = pywemo_device
    light.state = {"onoff": 0, "available": True}
    light.capabilities = ["onoff", "levelcontrol", "colortemperature"]
    pywemo_device.Lights = {pywemo_device.serialnumber: light}
    return light


async def test_async_update_locked_callback_and_update(
    hass, pywemo_bridge_light, wemo_entity, pywemo_device
):
    """Test that a callback and a state update request can't both happen at the same time."""
    await entity_test_helpers.test_async_update_locked_callback_and_update(
        hass,
        pywemo_device,
        wemo_entity,
    )


async def test_async_update_locked_multiple_updates(
    hass, pywemo_bridge_light, wemo_entity, pywemo_device
):
    """Test that two state updates do not proceed at the same time."""
    await entity_test_helpers.test_async_update_locked_multiple_updates(
        hass,
        pywemo_device,
        wemo_entity,
    )


async def test_async_update_locked_multiple_callbacks(
    hass, pywemo_bridge_light, wemo_entity, pywemo_device
):
    """Test that two device callback state updates do not proceed at the same time."""
    await entity_test_helpers.test_async_update_locked_multiple_callbacks(
        hass,
        pywemo_device,
        wemo_entity,
    )


async def test_available_after_update(
    hass, pywemo_registry, pywemo_device, pywemo_bridge_light, wemo_entity
):
    """Test the avaliability when an On call fails and after an update."""
    pywemo_bridge_light.turn_on.side_effect = pywemo.exceptions.ActionException
    pywemo_bridge_light.state["onoff"] = 1
    await entity_test_helpers.test_avaliable_after_update(
        hass, pywemo_registry, pywemo_device, wemo_entity, LIGHT_DOMAIN
    )


async def test_turn_off_state(hass, pywemo_bridge_light, wemo_entity):
    """Test that the device state is updated after turning off."""
    await entity_test_helpers.test_turn_off_state(hass, wemo_entity, LIGHT_DOMAIN)


async def test_light_update_entity(
    hass, pywemo_registry, pywemo_bridge_light, wemo_entity
):
    """Verify that the light performs state updates."""
    await async_setup_component(hass, HA_DOMAIN, {})

    # On state.
    pywemo_bridge_light.state["onoff"] = 1
    pywemo_bridge_light.state["temperature_mireds"] = 432
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    state = hass.states.get(wemo_entity.entity_id)
    assert state.attributes.get(ATTR_COLOR_TEMP) == 432
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.COLOR_TEMP]
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.COLOR_TEMP
    assert state.state == STATE_ON

    # Off state.
    pywemo_bridge_light.state["onoff"] = 0
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
