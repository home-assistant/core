"""The GIOS component."""

from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientConnectorError
from gios import Gios
from gios.exceptions import GiosError

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID, DOMAIN
from .coordinator import GiosConfigEntry, GiosData, GiosDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GiosConfigEntry) -> bool:
    """Set up GIOS as config entry."""
    station_id: int = entry.data[CONF_STATION_ID]
    _LOGGER.debug("Using station_id: %d", station_id)

    # We used to use int as config_entry unique_id, convert this to str.
    if isinstance(entry.unique_id, int):
        hass.config_entries.async_update_entry(entry, unique_id=str(station_id))  # type: ignore[unreachable]

    # We used to use int in device_entry identifiers, convert this to str.
    device_registry = dr.async_get(hass)
    old_ids = (DOMAIN, station_id)
    device_entry = device_registry.async_get_device(identifiers={old_ids})  # type: ignore[arg-type]
    if device_entry and entry.entry_id in device_entry.config_entries:
        new_ids = (DOMAIN, str(station_id))
        device_registry.async_update_device(device_entry.id, new_identifiers={new_ids})

    websession = async_get_clientsession(hass)
    try:
        gios = await Gios.create(websession, station_id)
    except (GiosError, ConnectionError, ClientConnectorError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                "entry": entry.title,
                "error": repr(err),
            },
        ) from err

    coordinator = GiosDataUpdateCoordinator(hass, entry, gios)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = GiosData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove air_quality entities from registry if they exist
    ent_reg = er.async_get(hass)
    unique_id = str(coordinator.gios.station_id)
    if entity_id := ent_reg.async_get_entity_id(
        AIR_QUALITY_PLATFORM, DOMAIN, unique_id
    ):
        _LOGGER.debug("Removing deprecated air_quality entity %s", entity_id)
        ent_reg.async_remove(entity_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GiosConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
