"""The Yale Access Bluetooth integration."""
from __future__ import annotations

import asyncio

import async_timeout
from yalexs_ble import PushLock

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import (
    LOCAL_NAME,
    BluetoothCallbackMatcher,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_KEY, CONF_SLOT, DISCOVERY_TIMEOUT, DOMAIN
from .models import YaleXSBLEData

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]

# We have 55s to find the lock, connect, and get status
# before we give up and raise ConfigEntryNotReady.
STARTUP_TIMEOUT = 55


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yale Access Bluetooth from a config entry."""
    local_name = entry.unique_id
    assert local_name is not None
    push_lock = PushLock(local_name, None, entry.data[CONF_KEY], entry.data[CONF_SLOT])
    push_lock.set_name(f"{entry.title} ({local_name})")
    startup_event = asyncio.Event()

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        push_lock.update_advertisement(service_info.device, service_info.advertisement)

    cancel_first_update = push_lock.register_callback(lambda *_: startup_event.set())
    entry.async_on_unload(await push_lock.start())

    # We may already have the advertisement, so check for it.
    for service_info in bluetooth.async_discovered_service_info(hass):
        if service_info.device.name == local_name:
            push_lock.update_advertisement(
                service_info.device, service_info.advertisement
            )
            break

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({LOCAL_NAME: local_name}),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    try:
        async with async_timeout.timeout(DISCOVERY_TIMEOUT):
            await startup_event.wait()
    except asyncio.TimeoutError as ex:
        raise ConfigEntryNotReady(
            f"{push_lock.last_error}; "
            f"Try moving the Bluetooth adapter closer to {local_name}."
        ) from ex
    finally:
        cancel_first_update()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = YaleXSBLEData(
        entry.title, local_name, push_lock
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data: YaleXSBLEData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
