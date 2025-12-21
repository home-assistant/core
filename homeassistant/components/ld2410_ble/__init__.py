"""The LD2410 BLE integration."""

import logging

from bleak_retry_connector import (
    BleakError,
    close_stale_connections_by_address,
    get_device,
)
from ld2410_ble import LD2410BLE

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import LD2410BLECoordinator
from .models import LD2410BLEConfigEntry, LD2410BLEData

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LD2410BLEConfigEntry) -> bool:
    """Set up LD2410 BLE from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    await close_stale_connections_by_address(address)

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), True
    ) or await get_device(address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find LD2410B device with address {address}"
        )

    ld2410_ble = LD2410BLE(ble_device)

    coordinator = LD2410BLECoordinator(hass, entry, ld2410_ble)

    try:
        await ld2410_ble.initialise()
    except BleakError as exc:
        raise ConfigEntryNotReady(
            f"Could not initialise LD2410B device with address {address}"
        ) from exc

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        ld2410_ble.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    entry.runtime_data = LD2410BLEData(entry.title, ld2410_ble, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await ld2410_ble.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: LD2410BLEConfigEntry
) -> None:
    """Handle options update."""
    if entry.title != entry.runtime_data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LD2410BLEConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.device.stop()

    return unload_ok
