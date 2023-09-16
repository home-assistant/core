"""The Decora BLE integration."""
from __future__ import annotations

import asyncio

from decora_bleak import DecoraBLEDevice, DecoraBLEError, IncorrectAPIKeyError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_API_KEY,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .models import DecoraBLEData

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Decora BLE from a config entry."""
    name: str = entry.title
    address: str = entry.data[CONF_ADDRESS]
    api_key: str = entry.data[CONF_API_KEY]

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Decora BLE device with address {address}"
        )

    decora_ble_device = DecoraBLEDevice(ble_device, api_key)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        decora_ble_device.update_device(service_info.device)
        hass.async_create_task(decora_ble_device.connect())

    shutdown_callback: CALLBACK_TYPE | None = await decora_ble_device.start()

    @callback
    def _async_shutdown(event: Event | None = None) -> None:
        """Notifies the device when Home Assistant is shutting down."""
        nonlocal shutdown_callback
        if shutdown_callback:
            shutdown_callback()
            shutdown_callback = None

    entry.async_on_unload(_async_shutdown)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    try:
        await decora_ble_device.wait_for_device_connection()
    except IncorrectAPIKeyError as ex:
        raise ConfigEntryAuthFailed(str(ex)) from ex
    except (DecoraBLEError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady(
            f"{ex}; Try moving the Bluetooth adapter closer to {name}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = DecoraBLEData(
        address,
        api_key,
        name=name,
        device=decora_ble_device,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await decora_ble_device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
