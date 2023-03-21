"""The Dormakaba dKey integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from py_dormakaba_dkey import DKEYLock
from py_dormakaba_dkey.errors import DKEY_EXCEPTIONS
from py_dormakaba_dkey.models import AssociationData

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ASSOCIATION_DATA, DOMAIN, UPDATE_SECONDS
from .models import DormakabaDkeyData

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dormakaba dKey from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find dKey device with address {address}")

    lock = DKEYLock(ble_device)
    lock.set_association_data(
        AssociationData.from_json(entry.data[CONF_ASSOCIATION_DATA])
    )

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        lock.set_ble_device_and_advertisement_data(
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
            await lock.update()
            await lock.disconnect()
        except DKEY_EXCEPTIONS as ex:
            raise UpdateFailed(str(ex)) from ex

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=lock.name,
        update_method=_async_update,
        update_interval=timedelta(seconds=UPDATE_SECONDS),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = DormakabaDkeyData(
        lock, coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await lock.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: DormakabaDkeyData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.lock.disconnect()

    return unload_ok
