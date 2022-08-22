"""Tests for the Lutron Caseta integration."""


from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_cover_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    await async_setup_integration(hass, MockBridge)

    cover_entity_id = "cover.basement_bedroom_left_shade"

    entity_registry = er.async_get(hass)

    # Assert that Caseta covers will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(cover_entity_id).unique_id == "000004d2_802"
