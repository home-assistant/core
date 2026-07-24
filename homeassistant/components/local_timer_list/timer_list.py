"""Local timer list platform."""

from homeassistant.components.timer_list import InMemoryTimerListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TIMER_LIST_NAME


# Kept as a named subclass so UI-created lists have a stable, distinct type.
class LocalTimerListEntity(InMemoryTimerListEntity):
    """A standalone, UI-created in-memory timer list."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the local timer list entity from a config entry."""
    async_add_entities(
        [
            LocalTimerListEntity(
                name=config_entry.data[CONF_TIMER_LIST_NAME],
                unique_id=config_entry.entry_id,
            )
        ]
    )
