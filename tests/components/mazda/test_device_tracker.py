"""The device tracker tests for the Mazda Connected Services integration."""
from homeassistant.components.device_tracker import ATTR_SOURCE_TYPE, SourceType
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_device_tracker(hass: HomeAssistant) -> None:
    """Test creation of the device tracker."""
    await init_integration(hass)

    entity_registry = er.async_get(hass)

    state = hass.states.get("device_tracker.my_mazda3_device_tracker")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Device tracker"
    assert state.attributes.get(ATTR_ICON) == "mdi:car"
    assert state.attributes.get(ATTR_LATITUDE) == 1.234567
    assert state.attributes.get(ATTR_LONGITUDE) == -2.345678
    assert state.attributes.get(ATTR_SOURCE_TYPE) == SourceType.GPS
    entry = entity_registry.async_get("device_tracker.my_mazda3_device_tracker")
    assert entry
    assert entry.unique_id == "JM000000000000000"
