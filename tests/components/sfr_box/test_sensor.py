"""Test the SFR Box sensors."""
from collections.abc import Generator
from types import MappingProxyType
from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import check_device_registry, check_entities
from .const import ATTR_DEFAULT_DISABLED, EXPECTED_ENTITIES

pytestmark = pytest.mark.usefixtures("system_get_info", "dsl_get_info")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None, None, None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", [Platform.SENSOR]):
        yield


def _check_and_enable_disabled_entities(
    entity_registry: er.EntityRegistry, expected_entities: MappingProxyType
) -> None:
    """Ensure that the expected_entities are correctly disabled."""
    for expected_entity in expected_entities:
        if expected_entity.get(ATTR_DEFAULT_DISABLED):
            entity_id = expected_entity[ATTR_ENTITY_ID]
            registry_entry = entity_registry.entities.get(entity_id)
            assert registry_entry, f"Registry entry not found for {entity_id}"
            assert registry_entry.disabled
            assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
            entity_registry.async_update_entity(entity_id, **{"disabled_by": None})


async def test_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for SFR Box sensors."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    check_device_registry(device_registry, EXPECTED_ENTITIES["expected_device"])

    expected_entities = EXPECTED_ENTITIES[Platform.SENSOR]
    assert len(entity_registry.entities) == len(expected_entities)

    _check_and_enable_disabled_entities(entity_registry, expected_entities)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities(hass, entity_registry, expected_entities)
