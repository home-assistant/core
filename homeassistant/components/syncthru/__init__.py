"""The syncthru component."""
from __future__ import annotations

import logging

from pysyncthru import SyncThru

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    session = aiohttp_client.async_get_clientsession(hass)
    printer = hass.data[DOMAIN][entry.entry_id] = SyncThru(
        entry.data[CONF_URL], session
    )

    try:
        await printer.update()
    except ValueError:
        _LOGGER.error(
            "Device at %s not appear to be a SyncThru printer, aborting setup",
            printer.url,
        )
        return False
    else:
        if printer.is_unknown_state():
            raise ConfigEntryNotReady

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=device_connections(printer),
        identifiers=device_identifiers(printer),
        model=printer.model(),
        name=printer.hostname(),
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def device_identifiers(printer: SyncThru) -> set[tuple[str, str]]:
    """Get device identifiers for device registry."""
    return {(DOMAIN, printer.serial_number())}


def device_connections(printer: SyncThru) -> set[tuple[str, str]]:
    """Get device connections for device registry."""
    connections = set()
    try:
        mac = printer.raw()["identity"]["mac_addr"]
        if mac:
            connections.add((dr.CONNECTION_NETWORK_MAC, mac))
    except AttributeError:
        pass
    return connections
