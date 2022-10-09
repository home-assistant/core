"""Tests for the Lutron Caseta integration."""


from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_button_unique_id(hass: HomeAssistant) -> None:
    """Test a button unique id."""
    await async_setup_integration(hass, MockBridge)

    ra3_button_entity_id = (
        "button.hallway_main_stairs_position_1_keypad_kitchen_pendants"
    )
    caseta_button_entity_id = "button.dining_room_pico_on"

    entity_registry = er.async_get(hass)

    # Assert that Caseta buttons will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(ra3_button_entity_id).unique_id == "000004d2_1372"
    assert (
        entity_registry.async_get(caseta_button_entity_id).unique_id == "000004d2_111"
    )
