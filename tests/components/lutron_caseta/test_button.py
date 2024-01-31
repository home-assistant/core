"""Tests for the Lutron Caseta integration."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_button_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a button unique id."""
    await async_setup_integration(hass, MockBridge)

    ra3_button_entity_id = (
        "button.hallway_main_stairs_position_1_keypad_kitchen_pendants"
    )
    caseta_button_entity_id = "button.dining_room_pico_stop"

    # Assert that Caseta buttons will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(ra3_button_entity_id).unique_id == "000004d2_1372"
    assert (
        entity_registry.async_get(caseta_button_entity_id).unique_id == "000004d2_111"
    )


async def test_button_press(hass: HomeAssistant) -> None:
    """Test a button press."""
    await async_setup_integration(hass, MockBridge)

    ra3_button_entity_id = (
        "button.hallway_main_stairs_position_1_keypad_kitchen_pendants"
    )

    state = hass.states.get(ra3_button_entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ra3_button_entity_id},
        blocking=False,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ra3_button_entity_id)
    assert state
