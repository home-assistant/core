"""The OpenRGB integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


def _setup_server_device_registry(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, coordinator: OpenRGBCoordinator
):
    """Set up device registry for the OpenRGB SDK Server."""
    device_registry = dr.async_get(hass)

    # Create the parent OpenRGB SDK Server device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        model="OpenRGB SDK Server",
        manufacturer="OpenRGB",
        sw_version=coordinator.get_client_protocol_version(),
        entry_type=dr.DeviceEntryType.SERVICE,
    )


async def async_setup_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Set up OpenRGB from a config entry."""
    coordinator = OpenRGBCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    _setup_server_device_registry(hass, entry, coordinator)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and hasattr(entry, "runtime_data"):
        await entry.runtime_data.async_client_disconnect()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove the config entry if the device is no longer connected."""
    coordinator = entry.runtime_data

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue

        # Block removal of the OpenRGB SDK Server device
        if identifier == entry.entry_id:
            return False

        # Block removal of the OpenRGB device if it is still connected
        if identifier in coordinator.data:
            return False

        return True

    # Not our device
    return True
