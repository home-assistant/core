"""The melnor integration."""

from __future__ import annotations

from melnor_bluetooth.device import Device

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import MelnorConfigEntry, MelnorDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: MelnorConfigEntry) -> bool:
    """Set up melnor from a config entry."""
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

    coordinator = MelnorDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MelnorConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.data.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
