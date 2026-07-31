"""The Duco integration."""

import re

from duco_connectivity import DucoClient

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import DucoConfigEntry, DucoCoordinator

_REMOVED_SENSOR_RE = re.compile(r"_\d+_(box_)?temperature$")


async def async_setup_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Set up Duco from a config entry."""
    # Clean up stale temperature registry entries so removed entities from the
    # python-duco-connectivity migration do not linger after upgrade.
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if _REMOVED_SENSOR_RE.search(entity_entry.unique_id):
            entity_registry.async_remove(entity_entry.entity_id)

    client = DucoClient(
        session=async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
    )

    coordinator = DucoCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Unload a Duco config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
