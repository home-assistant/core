"""The Hyperion component."""

import asyncio
import logging
from typing import Any, Dict, Tuple

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [LIGHT_DOMAIN]

_LOGGER = logging.getLogger(__name__)

# A config entry represents a connection to a single Hyperion server. The config
# entry_id is the server id returned from the Hyperion instance (a unique ID per
# server).
#
# Each server connection may create multiple entities, 1 per "instance" on the Hyperion
# server. The unique_id for each entity is <server id>:<instance #>, where <server_id>
# will be the unique_id on the relevant config entry (as above).
#
# The get_hyperion_unique_id method will create a per-entity unique id when given the
# server id and the instance number. The split_hyperion_unique_id will reverse the
# operation.


def get_hyperion_unique_id(server_id: str, instance: int) -> str:
    """Get a unique_id for a Hyperion instance."""
    return f"{server_id}:{instance}"


def split_hyperion_unique_id(unique_id) -> Tuple[str, int]:
    """Split a unique_id for a Hyperion instance."""
    try:
        server_id, instance = unique_id.rsplit(":", 1)
        return server_id, int(instance)
    except ValueError:
        return None


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up Hyperion component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Hyperion from a config entry."""
    # TODO: Put master Hyperion connection here?
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return unload_ok
