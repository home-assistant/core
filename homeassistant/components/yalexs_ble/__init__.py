"""The Yale Access Bluetooth integration."""
from __future__ import annotations

from yalexs_ble import PushLock, local_name_to_serial

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_KEY, CONF_SLOT, DOMAIN
from .models import YaleXSBLEData

PLATFORMS: list[Platform] = [Platform.LOCK]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yale Access Bluetooth from a config entry."""
    local_name = entry.unique_id
    assert local_name is not None
    key = entry.data[CONF_KEY]
    slot = entry.data[CONF_SLOT]

    push_lock = PushLock(local_name_to_serial(local_name))
    push_lock.set_lock_key(key, slot)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak
        | bluetooth.BluetoothServiceInfo,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        assert isinstance(service_info, bluetooth.BluetoothServiceInfoBleak)
        push_lock.update_advertisement(service_info.device, service_info.advertisement)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({"local_name": local_name}),
        )
    )
    entry.async_on_unload(await push_lock.start())

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = YaleXSBLEData(
        local_name, push_lock
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
