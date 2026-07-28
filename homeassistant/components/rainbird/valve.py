"""Support for Rain Bird Irrigation system LNK Wi-Fi Module."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_DURATION, CONF_IMPORTED_NAMES, CONF_ZONE_TYPE, ZONE_TYPE_VALVE
from .entity import RainBirdValve
from .types import RainbirdConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for Rain Bird irrigation valves."""
    if config_entry.options.get(CONF_ZONE_TYPE) != ZONE_TYPE_VALVE:
        return
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(
        RainBirdValve(
            coordinator,
            zone,
            config_entry.options[ATTR_DURATION],
            config_entry.data.get(CONF_IMPORTED_NAMES, {}).get(str(zone)),
        )
        for zone in coordinator.data.zones
    )
