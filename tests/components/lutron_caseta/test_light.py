"""Tests for the Lutron Caseta integration."""


from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_light_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    await async_setup_integration(hass, MockBridge)
    entity_id = "light.mock_title"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == "123"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
