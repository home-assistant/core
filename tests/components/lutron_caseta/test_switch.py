"""Tests for the Lutron Caseta integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_switch_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light unique id."""
    await async_setup_integration(hass, MockBridge)

    switch_entity_id = "switch.basement_bathroom_exhaust_fan"

    # Assert that Caseta covers will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(switch_entity_id).unique_id == "000004d2_803"
