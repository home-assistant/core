"""Tests for the Velbus component."""

from homeassistant.components.velbus import VelbusConfigEntry
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def get_entity_id(
    entity_registry: er.EntityRegistry, domain: str, unique_id: str
) -> str:
    """Return the entity_id for a Velbus entity unique_id."""
    entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None, f"missing {domain}.{DOMAIN} entity {unique_id!r}"
    return entity_id


async def init_integration(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
) -> None:
    """Load the Velbus integration."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
