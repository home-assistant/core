"""The syncthru component."""

from __future__ import annotations

from pysyncthru import SyncThru, SyncThruAPINotSupported

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import SyncthruCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    coordinator = SyncthruCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    if isinstance(coordinator.last_exception, SyncThruAPINotSupported):
        # this means that the printer does not support the syncthru JSON API
        # and the config should simply be discarded
        return False

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        configuration_url=coordinator.syncthru.url,
        connections=device_connections(coordinator.syncthru),
        manufacturer="Samsung",
        identifiers=device_identifiers(coordinator.syncthru),
        model=coordinator.syncthru.model(),
        name=coordinator.syncthru.hostname(),
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
