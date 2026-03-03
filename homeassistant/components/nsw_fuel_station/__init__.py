"""The NSW Fuel Check component."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any, cast

from nsw_tas_fuel import NSWFuelApiClient

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import NSWFuelCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import NSWFuelConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
# Stations appear to update at random, it could be days between price changes
DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=720)


async def async_setup_entry(hass: HomeAssistant, entry: NSWFuelConfigEntry) -> bool:
    """Set up NSW Fuel Check integration from the config entry."""
    client_id = cast("str", entry.data.get(CONF_CLIENT_ID))
    client_secret = cast("str", entry.data.get(CONF_CLIENT_SECRET))
    nicknames: dict[str, dict[str, Any]] = entry.data.get("nicknames", {})

    session = async_get_clientsession(hass)

    api = NSWFuelApiClient(
        session=session,
        client_id=client_id,
        client_secret=client_secret,
    )

    coordinator = NSWFuelCoordinator(
        hass=hass,
        api=api,
        nicknames=nicknames,
        scan_interval=DEFAULT_SCAN_INTERVAL,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        _LOGGER.warning("Initial data fetch failed: %s", err)
        raise

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: NSWFuelConfigEntry) -> None:
    """Reload after new entity added to existing service/location/nickname."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSWFuelConfigEntry) -> bool:
    """Temporarily remove config entry e.g. disable integration etc."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: NSWFuelConfigEntry) -> None:
    """Permanently remove config entry and clean up orphan entities."""
    entity_registry = er.async_get(hass)

    for entity_entry in list(entity_registry.entities.values()):
        if entity_entry.config_entry_id == entry.entry_id:
            entity_registry.async_remove(entity_entry.entity_id)

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
