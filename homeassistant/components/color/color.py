"""Platform for the Color helper, one entity per config entry."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ColorConfigEntry, ColorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ColorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the color entity from a config entry."""
    entity = ColorEntity(entry)
    entry.runtime_data = entity
    async_add_entities([entity])
