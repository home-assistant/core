"""The Ooler Sleep System integration."""
from __future__ import annotations

from ooler_ble_client import OolerBLEDevice

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.components.bluetooth.match import ADDRESS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback

from .const import CONF_MODEL, DOMAIN
from .models import OolerData

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ooler from a config entry."""
    address = entry.unique_id
    assert address is not None

    model = entry.data[CONF_MODEL]
    client = OolerBLEDevice(model=model)

    @callback
    def _async_update_ble(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        client.set_ble_device(service_info.device)
        hass.async_create_task(client.connect())

    entry.async_on_unload(
        async_register_callback(
            hass,
            _async_update_ble,
            {ADDRESS: address},
            BluetoothScanningMode.ACTIVE,
        )
    )

    # def _unavailable_callback(info: BluetoothServiceInfoBleak) -> None:
    #     _LOGGER.error("%s is no longer seen", info.address)
    #     hass.async_create_task(client.connect())

    # entry.async_on_unload(
    #     async_track_unavailable(hass, _unavailable_callback, address, connectable=True)
    # )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = OolerData(
        address,
        model,
        client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await client.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
