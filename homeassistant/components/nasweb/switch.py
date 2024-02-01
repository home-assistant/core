"""Platform for NASweb output."""
from __future__ import annotations

import logging

from webio_api import Output as NASwebOutput
from webio_api.const import KEY_OUTPUTS

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN
from .nasweb_data import NASwebData
from .relay_switch import RelaySwitch

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up switch platform."""
    nasweb_data: NASwebData = hass.data[DOMAIN]
    coordinator = nasweb_data.entries_coordinators[config.entry_id]
    nasweb_outputs = coordinator.data[KEY_OUTPUTS]
    coordinator.async_add_switch_callback = async_add_entities
    entities: list[RelaySwitch] = []
    for out in nasweb_outputs:
        if not isinstance(out, NASwebOutput):
            _LOGGER.error("Cannot create RelaySwitch entity without NASwebOutput")
            continue
        new_output = RelaySwitch(coordinator, out)
        entities.append(new_output)
    async_add_entities(entities)
