"""The LED BLE integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from led_ble import BLEAK_EXCEPTIONS, LEDBLE

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICE_TIMEOUT, DOMAIN, UPDATE_SECONDS
from .models import LEDBLEData

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LED BLE from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find LED BLE device with address {address}"
        )

    led_ble = LEDBLE(ble_device)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        led_ble.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    async def _async_update() -> None:
        """Update the device state."""
        try:
            await led_ble.update()
        except BLEAK_EXCEPTIONS as ex:
            raise UpdateFailed(str(ex)) from ex

    startup_event = asyncio.Event()
    cancel_first_update = led_ble.register_callback(lambda *_: startup_event.set())
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=led_ble.name,
        update_method=_async_update,
        update_interval=timedelta(seconds=UPDATE_SECONDS),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        cancel_first_update()
        raise

    try:
        async with asyncio.timeout(DEVICE_TIMEOUT):
            await startup_event.wait()
    except TimeoutError as ex:
        raise ConfigEntryNotReady(
            "Unable to communicate with the device; "
            f"Try moving the Bluetooth adapter closer to {led_ble.name}"
        ) from ex
    finally:
        cancel_first_update()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = LEDBLEData(
        entry.title, led_ble, coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await led_ble.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
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
