"""The LED BLE integration."""
from __future__ import annotations

import asyncio

import async_timeout
from led_ble import BLEAK_EXCEPTIONS, LEDBLE

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEVICE_TIMEOUT, DOMAIN
from .models import LEDBLEData

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yale Access Bluetooth from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find LED BLE device with address {address}"
        )

    led_ble = LEDBLE(ble_device)

    startup_event = asyncio.Event()

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        led_ble.set_ble_device(service_info.device)

    cancel_first_update = led_ble.register_callback(lambda *_: startup_event.set())
    try:
        await led_ble.update()
    except BLEAK_EXCEPTIONS as ex:
        raise ConfigEntryNotReady from ex

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    try:
        async with async_timeout.timeout(DEVICE_TIMEOUT):
            await startup_event.wait()
    except asyncio.TimeoutError as ex:
        raise ConfigEntryNotReady(
            "Could not update; "
            f"Try moving the Bluetooth adapter closer to {led_ble.name}"
        ) from ex
    finally:
        cancel_first_update()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = LEDBLEData(entry.title, led_ble)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data: LEDBLEData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: LEDBLEData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.device.stop()

    return unload_ok
