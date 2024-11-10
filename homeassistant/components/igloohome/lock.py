"""Implementation of the lock platform."""

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Do setup the lock entities."""

    entities = [GenericLock()]

    async_add_entities(entities)


class GenericLock(LockEntity):
    """Implementation of a generic lock."""
