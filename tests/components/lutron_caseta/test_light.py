"""Tests for the Lutron Caseta integration."""

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_light_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light unique id."""
    await async_setup_integration(hass, MockBridge)

    ra3_entity_id = "light.basement_bedroom_main_lights"
    caseta_entity_id = "light.kitchen_main_lights"

    # Assert that RA3 lights will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(ra3_entity_id).unique_id == "000004d2_801"

    # Assert that Caseta lights will have the serial number as the uniqueID
    assert entity_registry.async_get(caseta_entity_id).unique_id == "5442321"

    state = hass.states.get(ra3_entity_id)
    assert state.state == STATE_ON


async def test_previous_brightness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test brightness tracked and restored."""
    await async_setup_integration(hass, MockBridge)

    # Initially, off with no brightness
    caseta_entity_id = "light.kitchen_other_lights"

    state = hass.states.get(caseta_entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_BRIGHTNESS] is None

    # Turn on, expect this defaults to 50% (255/2) or 100% (255)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(caseta_entity_id)

    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    # Set brightness to 10% (25)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: caseta_entity_id, ATTR_BRIGHTNESS: 25},
        blocking=True,
    )
    await hass.async_block_till_done()
