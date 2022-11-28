"""The melnor integration."""

from __future__ import annotations

from melnor_bluetooth.device import Device

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .models import MelnorDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up melnor from a config entry."""

    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    ble_device = bluetooth.async_ble_device_from_address(hass, entry.data[CONF_ADDRESS])

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Couldn't find a nearby device for address: {entry.data[CONF_ADDRESS]}"
        )

    # Create the device and connect immediately so we can pull down
    # required attributes before building out our entities
    device = Device(ble_device)
    await device.connect(retry_attempts=4)

    if not device.is_connected:
        raise ConfigEntryNotReady(f"Failed to connect to: {device.mac}")

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        device.update_ble_device(service_info.device)

    bluetooth.async_register_callback(
        hass,
        _async_update_ble,
        BluetoothCallbackMatcher(address=device.mac),
        bluetooth.BluetoothScanningMode.PASSIVE,
    )

    coordinator = MelnorDataUpdateCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    device: Device = hass.data[DOMAIN][entry.entry_id].data

    await device.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
