"""Tests for the entity platform."""

from contextlib import nullcontext

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_HUMIDIFIER

from tests.common import MockConfigEntry

NoException = nullcontext()


async def test_base_unique_id(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that unique_id is based on subDeviceNo."""
    # vesync-device.json defines subDeviceNo for 200s-humidifier as 4321.
    entity = entity_registry.async_get(ENTITY_HUMIDIFIER)
    assert entity.unique_id.endswith("4321")
