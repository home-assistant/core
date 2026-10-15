"""The iBeacon tracker integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .const import DOMAIN, PLATFORMS
from .coordinator import IBeaconCoordinator

type IBeaconConfigEntry = ConfigEntry[IBeaconCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IBeaconConfigEntry) -> None:
    """Set up Bluetooth LE Tracker from a config entry."""
    entry.runtime_data = coordinator = IBeaconCoordinator(
        hass, entry, dr.async_get(hass)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: IBeaconConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Remove iBeacon config entry from a device."""
    coordinator = config_entry.runtime_data
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN and coordinator.async_device_id_seen(identifier[1])
    )
