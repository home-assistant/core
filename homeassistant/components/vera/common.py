"""Common vera code."""
import logging
from typing import DefaultDict, List, NamedTuple, Set

import pyvera as pv

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LEGACY_UNIQUE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ControllerData(NamedTuple):
    """Controller data."""

    controller: pv.VeraController
    devices: DefaultDict[str, List[pv.VeraDevice]]
    scenes: List[pv.VeraScene]
    config_entry: ConfigEntry


def get_configured_platforms(controller_data: ControllerData) -> Set[str]:
    """Get configured platforms for a controller."""
    platforms = []
    for platform in controller_data.devices:
        platforms.append(platform)

    if controller_data.scenes:
        platforms.append(SCENE_DOMAIN)

    return set(platforms)


def get_controller_data(hass: HomeAssistant, config_unique_id: str) -> ControllerData:
    """Get controller data from hass data."""
    return hass.data.setdefault(DOMAIN, {})[config_unique_id]


def set_controller_data(
    hass: HomeAssistant, config_unique_id: str, data: ControllerData
) -> None:
    """Set controller data in hass data."""
    hass.data.setdefault(DOMAIN, {})[config_unique_id] = data


async def async_maybe_set_legacy_entity_unique_id(
    hass: HomeAssistant, config_entry: ConfigEntry, value: bool
) -> None:
    """Set a config entry to use legacy entity unique_id generation.

    Only sets the value if a value is not already in place.
    """
    if config_entry.data.get(CONF_LEGACY_UNIQUE_ID) is not None:
        return

    _LOGGER.info("Setting vera controller %s = %s", CONF_LEGACY_UNIQUE_ID, value)

    config_entry.data = {**config_entry.data, **{CONF_LEGACY_UNIQUE_ID: value}}

    hass.config_entries.async_update_entry(entry=config_entry, data=config_entry.data)
