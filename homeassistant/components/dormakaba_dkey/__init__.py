"""The Dormakaba dKey integration."""

from __future__ import annotations

from py_dormakaba_dkey import DKEYLock
from py_dormakaba_dkey.models import AssociationData

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_ASSOCIATION_DATA
from .coordinator import DormakabaDkeyConfigEntry, DormakabaDkeyCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: DormakabaDkeyConfigEntry
) -> bool:
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

    coordinator = DormakabaDkeyCoordinator(hass, entry, lock)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await lock.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    entry.async_on_unload(coordinator.lock.disconnect)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DormakabaDkeyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
