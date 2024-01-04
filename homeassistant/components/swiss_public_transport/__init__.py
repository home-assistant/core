"""The swiss_public_transport component."""
import logging

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)

from homeassistant import config_entries, core
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DESTINATION, CONF_START, DOMAIN
from .coordinator import SwissPublicTransportDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up Swiss public transport from a config entry."""
    config = entry.data

    start = config[CONF_START]
    destination = config[CONF_DESTINATION]

    session = async_get_clientsession(hass)
    opendata = OpendataTransport(start, destination, session)

    try:
        await opendata.async_get_data()
    except OpendataTransportConnectionError as e:
        raise ConfigEntryNotReady(
            f"Timeout while connecting for entry '{start} {destination}'"
        ) from e
    except OpendataTransportError as e:
        _LOGGER.error(
            "Setup failed for entry '%s %s', check at http://transport.opendata.ch/examples/stationboard.html if your station names are valid",
            start,
            destination,
        )
        raise ConfigEntryError(
            f"Setup failed for entry '{start} {destination}' with invalid data"
        ) from e

    coordinator = SwissPublicTransportDataUpdateCoordinator(hass, opendata)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Migrate config entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 3:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new = {**config_entry.data}

        # Remove wrongly registered devices
        device_registry = dr.async_get(hass)
        device_entries = dr.async_entries_for_config_entry(
            device_registry, config_entry_id=config_entry.entry_id
        )
        for dev in device_entries:
            device_registry.async_remove_device(dev.id)

        # Set a valid unique id for config entries
        config_entry.unique_id = (
            f"{config_entry.data[CONF_START]} {config_entry.data[CONF_DESTINATION]}"
        )

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
