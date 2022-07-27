"""The Yale Access Bluetooth integration."""
from __future__ import annotations

import asyncio
import logging

from yalexs_ble import PushLock

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import (
    LOCAL_NAME,
    BluetoothCallbackMatcher,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_KEY, CONF_SLOT, DOMAIN
from .models import YaleXSBLEData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LOCK]

STARTUP_TIMEOUT = 9


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yale Access Bluetooth from a config entry."""
    local_name = entry.unique_id
    assert local_name is not None
    key = entry.data[CONF_KEY]
    slot = entry.data[CONF_SLOT]
    push_lock = PushLock(local_name)
    push_lock.set_lock_key(key, slot)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = YaleXSBLEData(
        entry.title, local_name, push_lock
    )
    startup_event = asyncio.Event()

    # Platforms need to subscribe first
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak
        | bluetooth.BluetoothServiceInfo,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        assert isinstance(service_info, bluetooth.BluetoothServiceInfoBleak)
        push_lock.update_advertisement(service_info.device, service_info.advertisement)
        if not startup_event.is_set():
            startup_event.set()

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({LOCAL_NAME: local_name}),
        )
    )
    entry.async_on_unload(await push_lock.start())

    # We don't want the overhead of tearing down and trying
    # again since the BLE device may take a while to discover,
    # but if we can avoid setting up in an unavailable state
    # because the device just hasn't been discovered yet, we
    # try to wait a bit for bluetooth discovery to finish.
    try:
        await asyncio.wait_for(startup_event.wait(), timeout=STARTUP_TIMEOUT)
    except asyncio.TimeoutError:
        _LOGGER.debug(
            "%s: Timeout waiting for startup, starting up in an unavailable state",
            local_name,
        )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: YaleXSBLEData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != coordinator.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
