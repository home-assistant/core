"""The syncthru component."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pysyncthru import ConnectionMode, SyncThru, SyncThruAPINotSupported

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    session = aiohttp_client.async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    printer = SyncThru(
        entry.data[CONF_URL], session, connection_mode=ConnectionMode.API
    )

    async def async_update_data() -> SyncThru:
        """Fetch data from the printer."""
        try:
            async with asyncio.timeout(10):
                await printer.update()
        except SyncThruAPINotSupported as api_error:
            # if an exception is thrown, printer does not support syncthru
            _LOGGER.debug(
                "Configured printer at %s does not provide SyncThru JSON API",
                printer.url,
                exc_info=api_error,
            )
            raise

        # if the printer is offline, we raise an UpdateFailed
        if printer.is_unknown_state():
            raise UpdateFailed(f"Configured printer at {printer.url} does not respond.")
        return printer

    coordinator = DataUpdateCoordinator[SyncThru](
        hass,
        _LOGGER,
        config_entry=entry,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    if isinstance(coordinator.last_exception, SyncThruAPINotSupported):
        # this means that the printer does not support the syncthru JSON API
        # and the config should simply be discarded
        return False

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        configuration_url=printer.url,
        connections=device_connections(printer),
        manufacturer="Samsung",
        identifiers=device_identifiers(printer),
        model=printer.model(),
        name=printer.hostname(),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


def device_identifiers(printer: SyncThru) -> set[tuple[str, str]] | None:
    """Get device identifiers for device registry."""
    serial = printer.serial_number()
    if serial is None:
        return None
    return {(DOMAIN, serial)}


def device_connections(printer: SyncThru) -> set[tuple[str, str]]:
    """Get device connections for device registry."""
    if mac := printer.raw().get("identity", {}).get("mac_addr"):
        return {(dr.CONNECTION_NETWORK_MAC, mac)}
    return set()
