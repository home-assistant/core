"""Test Velux light entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.LIGHT


@pytest.mark.usefixtures("setup_integration")
async def test_light_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_light: AsyncMock,
) -> None:
    """Test light entity setup and device association."""

    test_entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"

    # check for entity existence and its name is equal to node name (light is "main feature")
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.attributes.get("friendly_name") == mock_light.name

    # Get entity + device entry
    entity_entry = entity_registry.async_get(test_entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None

    # Verify device has correct identifiers + name
    assert ("velux", mock_light.serial_number) in device_entry.identifiers
    assert device_entry.name == mock_light.name
