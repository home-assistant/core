"""Tests for the Wemo fan entity."""

import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.wemo import fan
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from . import entity_test_helpers


@pytest.fixture
def pywemo_model():
    """Pywemo Humidifier models use the fan platform."""
    return "Humidifier"


# Tests that are in common among wemo platforms. These test methods will be run
# in the scope of this test module. They will run using the pywemo_model from
# this test module (Humidifier).
test_async_update_locked_multiple_updates = (
    entity_test_helpers.test_async_update_locked_multiple_updates
)
test_async_update_locked_multiple_callbacks = (
    entity_test_helpers.test_async_update_locked_multiple_callbacks
)
test_async_update_locked_callback_and_update = (
    entity_test_helpers.test_async_update_locked_callback_and_update
)
test_async_locked_update_with_exception = (
    entity_test_helpers.test_async_locked_update_with_exception
)
test_async_update_with_timeout_and_recovery = (
    entity_test_helpers.test_async_update_with_timeout_and_recovery
)


async def test_fan_registry_state_callback(
    hass, pywemo_registry, pywemo_device, wemo_entity
):
    """Verify that the fan receives state updates from the registry."""
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


async def test_fan_update_entity(hass, pywemo_registry, pywemo_device, wemo_entity):
    """Verify that the fan performs state updates."""
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


async def test_fan_reset_filter_service(hass, pywemo_device, wemo_entity):
    """Verify that SERVICE_RESET_FILTER_LIFE is registered and works."""
    assert await hass.services.async_call(
        DOMAIN,
        fan.SERVICE_RESET_FILTER_LIFE,
        {ATTR_ENTITY_ID: wemo_entity.entity_id},
        blocking=True,
    )
    pywemo_device.reset_filter_life.assert_called_with()


@pytest.mark.parametrize(
    "test_input,expected",
    [
        (0, fan.WEMO_HUMIDITY_45),
        (45, fan.WEMO_HUMIDITY_45),
        (50, fan.WEMO_HUMIDITY_50),
        (55, fan.WEMO_HUMIDITY_55),
        (60, fan.WEMO_HUMIDITY_60),
        (100, fan.WEMO_HUMIDITY_100),
    ],
)
async def test_fan_set_humidity_service(
    hass, pywemo_device, wemo_entity, test_input, expected
):
    """Verify that SERVICE_SET_HUMIDITY is registered and works."""
    assert await hass.services.async_call(
        DOMAIN,
        fan.SERVICE_SET_HUMIDITY,
        {
            ATTR_ENTITY_ID: wemo_entity.entity_id,
            fan.ATTR_TARGET_HUMIDITY: test_input,
        },
        blocking=True,
    )
    pywemo_device.set_humidity.assert_called_with(expected)
