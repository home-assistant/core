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


@pytest.fixture
def pywemo_model():
    """Pywemo Humidifier models use the fan platform."""
    return "Humidifier"


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
        {fan.ATTR_ENTITY_ID: wemo_entity.entity_id},
        blocking=True,
    )
    pywemo_device.reset_filter_life.assert_called_with()


async def test_fan_set_humidity_service(hass, pywemo_device, wemo_entity):
    """Verify that SERVICE_SET_HUMIDITY is registered and works."""
    assert await hass.services.async_call(
        DOMAIN,
        fan.SERVICE_SET_HUMIDITY,
        {
            fan.ATTR_ENTITY_ID: wemo_entity.entity_id,
            fan.ATTR_TARGET_HUMIDITY: "50",
        },
        blocking=True,
    )
    pywemo_device.set_humidity.assert_called_with(fan.WEMO_HUMIDITY_50)
