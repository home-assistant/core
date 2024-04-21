"""Tests for the Wemo standalone/non-bridge light entity."""

import pytest
from pywemo.exceptions import ActionException

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import entity_test_helpers


@pytest.fixture
def pywemo_model():
    """Pywemo Dimmer models use the light platform (WemoDimmer class)."""
    return "Dimmer"


# Tests that are in common among wemo platforms. These test methods will be run
# in the scope of this test module. They will run using the pywemo_model from
# this test module (Dimmer).
test_async_update_locked_multiple_updates = (
    entity_test_helpers.test_async_update_locked_multiple_updates
)
test_async_update_locked_multiple_callbacks = (
    entity_test_helpers.test_async_update_locked_multiple_callbacks
)
test_async_update_locked_callback_and_update = (
    entity_test_helpers.test_async_update_locked_callback_and_update
)


async def test_available_after_update(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Test the availability when an On call fails and after an update."""
    pywemo_device.on.side_effect = ActionException
    pywemo_device.get_state.return_value = 1
    await entity_test_helpers.test_avaliable_after_update(
        hass, pywemo_registry, pywemo_device, wemo_entity, LIGHT_DOMAIN
    )


async def test_turn_off_state(hass: HomeAssistant, wemo_entity) -> None:
    """Test that the device state is updated after turning off."""
    await entity_test_helpers.test_turn_off_state(hass, wemo_entity, LIGHT_DOMAIN)


async def test_turn_on_brightness(
    hass: HomeAssistant, pywemo_device, wemo_entity
) -> None:
    """Test setting the brightness value of the light."""
    brightness = 0
    state = 0

    def set_brightness(b):
        nonlocal brightness
        nonlocal state
        brightness, state = (b, int(bool(b)))

    pywemo_device.get_state.side_effect = lambda: state
    pywemo_device.get_brightness.side_effect = lambda: brightness
    pywemo_device.set_brightness.side_effect = set_brightness

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id], ATTR_BRIGHTNESS: 204},
        blocking=True,
    )

    pywemo_device.set_brightness.assert_called_once_with(80)
    states = hass.states.get(wemo_entity.entity_id)
    assert states.state == STATE_ON
    assert states.attributes[ATTR_BRIGHTNESS] == 204


async def test_light_registry_state_callback(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Verify that the light receives state updates from the registry."""
    # On state.
    pywemo_device.get_state.return_value = 1
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


async def test_light_update_entity(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Verify that the light performs state updates."""
    await async_setup_component(hass, HA_DOMAIN, {})

    # On state.
    pywemo_device.get_state.return_value = 1
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
