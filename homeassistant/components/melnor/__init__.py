"""The melnor integration."""


from melnor_bluetooth.device import Device

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_CONNECTION_TIMEOUT, DOMAIN
from .models import MelnorDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up melnor from a config entry."""

    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    ble_device = bluetooth.async_ble_device_from_address(hass, entry.data[CONF_ADDRESS])

    # Create the device and connect immediately so we can pull down
    # required attributes before building out our entities
    device = Device(entry.data[CONF_ADDRESS], ble_device)
    await device.connect(timeout=DEFAULT_CONNECTION_TIMEOUT)

    if not device.is_connected:
        raise ConfigEntryNotReady(f"Failed to connect to: {device.mac}")

    coordinator = MelnorDataUpdateCoordinator(hass, device)

    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    device: Device = hass.data[DOMAIN][entry.entry_id]["coordinator"].data

    await device.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    bluetooth.async_rediscover_address(hass, device.mac)

    return unload_ok
