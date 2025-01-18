"""Common test helpers for incomfort integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def async_setup_and_enable_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Enable all incomfort entities."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    # enable all entities
    entities = entity_registry.entities.get_entries_for_config_entry_id(
        mock_config_entry.entry_id
    )
    for entity in entities:
        if not entity.disabled:
            continue
        entity_registry.async_update_entity(entity.entity_id, disabled_by=None)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
