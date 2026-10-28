"""Support for select platform for Hue scenes (V2 only)."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bridge import HueConfigEntry
from .v2.select import async_setup_entry as setup_entry_v2

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hue select entities."""
    bridge = config_entry.runtime_data
    if bridge.api_version == 1:
        # should not happen, but just in case
        raise NotImplementedError("Select support is only available for V2 bridges")
    await setup_entry_v2(hass, config_entry, async_add_entities)
