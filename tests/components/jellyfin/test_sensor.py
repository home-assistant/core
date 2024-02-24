"""Tests for the Jellyfin sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_watching(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
) -> None:
    """Test the Jellyfin watching sensor."""
    state = hass.states.get("sensor.jellyfin_server")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "JELLYFIN-SERVER"
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Watching"
    assert state.state == "3"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.entity_category is None
    assert entry.unique_id == "SERVER-UUID-watching"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.connections == set()
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "SERVER-UUID")}
    assert device.manufacturer == "Jellyfin"
    assert device.name == "JELLYFIN-SERVER"
    assert device.sw_version is None
