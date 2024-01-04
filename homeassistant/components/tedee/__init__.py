"""Init the tedee component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import TedeeApiCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration setup."""

    coordinator = TedeeApiCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.bridge.serial)},
        manufacturer="Tedee",
        name=coordinator.bridge.name,
        model="Bridge",
        serial_number=coordinator.bridge.serial,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    def cleanup_disconnected_locks() -> None:
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        devices_to_remove = devices.copy()
        for device in devices:
            if device.model == "Bridge":
                devices_to_remove.remove(device)
            for lock in coordinator.data.values():
                if lock.lock_name == device.name:
                    devices_to_remove.remove(device)
                    break

        for device in devices_to_remove:
            device_registry.async_remove_device(device.id)

    cleanup_disconnected_locks()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
