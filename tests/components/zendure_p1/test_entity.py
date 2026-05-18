"""Tests for the Zendure Smart Meter P1 base entity."""

import pytest

from homeassistant.components.zendure_p1.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that all entities belong to a single correctly-registered device."""
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "SN123456")})
    assert device_entry is not None
    assert device_entry.manufacturer == "Zendure"
    assert device_entry.name == "Smart Meter P1"

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) == 4
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id
