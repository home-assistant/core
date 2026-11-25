"""The text platform for APsystems local API integration."""

from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ApSystemsConfigEntry
from .lake6.coordinator import Lake6ConfigEntry, Lake6RuntimeData
from .lake6.text import async_setup_entry as async_setup_lake6


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the text platform.

    EZ1 has no text entities and the platform is only forwarded for Lake_6
    entries; the guard keeps this a no-op if that ever changes.
    """
    if not isinstance(config_entry.runtime_data, Lake6RuntimeData):
        return
    await async_setup_lake6(hass, cast(Lake6ConfigEntry, config_entry), add_entities)
