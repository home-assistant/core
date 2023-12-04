"""Tests for sensor module in Sveriges Radio integrations."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_entity_registry(
    hass: HomeAssistant, async_setup_sr, entity_registry: er.EntityRegistry
) -> None:
    """Test that all 4 sensors are registered."""

    await async_setup_sr()

    assert "sensor.sveriges_radio_message" in entity_registry.entities
    assert "sensor.sveriges_radio_area" in entity_registry.entities
    assert "sensor.sveriges_radio_timestamp" in entity_registry.entities
    assert "sensor.sveriges_radio_exact_location" in entity_registry.entities
