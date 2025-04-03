"""Tests for sensors."""

# from unittest.mock import MagicMock

# from homeassistant.core import HomeAssistant
# from homeassistant.helpers import entity_registry as er

# from tests.common import MockConfigEntry


# async def test_entity_state(
#     hass: HomeAssistant,
#     entity_registry: er.EntityRegistry,
#     mock_device: MagicMock,
#     mock_integration: MockConfigEntry,
# ) -> None:
#     """Tests entity state is registered."""
#     state = hass.states.get("sensor.kat_bulgaria_power_status")
#     assert state
#     assert entity_registry.async_get(state.entity_id)
