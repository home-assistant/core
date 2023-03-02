"""The Yale Access Bluetooth integration."""
from __future__ import annotations

import asyncio

from yalexs_ble import (
    AuthError,
    ConnectionInfo,
    LockInfo,
    LockState,
    PushLock,
    YaleXSBLEError,
    local_name_is_unique,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_KEY, CONF_LOCAL_NAME, CONF_SLOT, DEVICE_TIMEOUT, DOMAIN
from .models import YaleXSBLEData
from .util import async_find_existing_service_info, bluetooth_callback_matcher

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yale Access Bluetooth from a config entry."""
    local_name = entry.data[CONF_LOCAL_NAME]
    address = entry.data[CONF_ADDRESS]
    key = entry.data[CONF_KEY]
    slot = entry.data[CONF_SLOT]
    has_unique_local_name = local_name_is_unique(local_name)
    push_lock = PushLock(local_name, address, None, key, slot)
    id_ = local_name if has_unique_local_name else address
    push_lock.set_name(f"{entry.title} ({id_})")

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        push_lock.update_advertisement(service_info.device, service_info.advertisement)

    entry.async_on_unload(await push_lock.start())

    # We may already have the advertisement, so check for it.
    if service_info := async_find_existing_service_info(hass, local_name, address):
        push_lock.update_advertisement(service_info.device, service_info.advertisement)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            bluetooth_callback_matcher(local_name, push_lock.address),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    try:
        await push_lock.wait_for_first_update(DEVICE_TIMEOUT)
    except AuthError as ex:
        raise ConfigEntryAuthFailed(str(ex)) from ex
    except (YaleXSBLEError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady(
            f"{ex}; Try moving the Bluetooth adapter closer to {local_name}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = YaleXSBLEData(
        entry.title, push_lock
    )

    @callback
    def _async_device_unavailable(
        _service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        """Handle device not longer being seen by the bluetooth stack."""
        push_lock.reset_advertisement_state()

    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass, _async_device_unavailable, push_lock.address
        )
    )

    @callback
    def _async_state_changed(
        new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Handle state changed."""
        if new_state.auth and not new_state.auth.successful:
            entry.async_start_reauth(hass)

    entry.async_on_unload(push_lock.register_callback(_async_state_changed))
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
