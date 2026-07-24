"""Tests for the JVC Projector binary sensor device."""

from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_MAC, MOCK_MAC_FORMATED

from tests.common import MockConfigEntry

ENTITY_ID = "binary_sensor.jvc_projector_power"


async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Tests entity state is registered."""
    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity_registry.async_get(entity.entity_id)


async def test_migrate_old_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests power binary sensor unique id is reformatted."""
    mock_config_entry.add_to_hass(hass)

    # Entity to be migrated
    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}_power",
        config_entry=mock_config_entry,
        suggested_object_id="jvc_projector_power",
    )

    # Ignored entity to get to 100% coverage
    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}_ignore",
        config_entry=mock_config_entry,
        suggested_object_id="jvc_projector_ignore",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    entry = entity_registry.async_get(entity.entity_id)
    assert entry
    assert entry.unique_id == f"{MOCK_MAC_FORMATED}_power"
