"""The RYSE integration."""

from bleak import BleakError
from bleak.backends.device import BLEDevice
from ryseble.device import RyseBLEDevice

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
    async_scanner_by_source,
    async_scanner_devices_by_address,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

type RyseConfigEntry = ConfigEntry[RyseBLEDevice]

PLATFORMS = [Platform.COVER]


def _async_local_ble_device(hass: HomeAssistant, address: str) -> BLEDevice | None:
    """Return the BLEDevice seen by a local adapter, ignoring Bluetooth proxies.

    ``ryseble.pair()`` registers a BlueZ Agent1 on the Home Assistant host, which
    cannot answer pairing for a device reached through an ESPHome/Shelly proxy.
    """
    for scanner_device in async_scanner_devices_by_address(
        hass, address, connectable=True
    ):
        if isinstance(scanner_device.scanner, BaseHaRemoteScanner):
            continue
        return scanner_device.ble_device
    return None


async def async_setup_entry(hass: HomeAssistant, entry: RyseConfigEntry) -> bool:
    """Set up RYSE."""
    address = entry.unique_id
    assert address is not None

    ble_device = _async_local_ble_device(hass, address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find RYSE device with address {address} on a local "
            "Bluetooth adapter"
        )

    device = RyseBLEDevice(ble_device)
    try:
        if not await device.pair():
            await device.unpair()
            raise ConfigEntryNotReady(
                f"Could not connect to RYSE device with address {address}"
            )
    except (TimeoutError, OSError, EOFError, BleakError) as err:
        await device.unpair()
        raise ConfigEntryNotReady(
            f"Could not connect to RYSE device with address {address}"
        ) from err

    entry.runtime_data = device

    @callback
    def _async_update_ble_device(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Refresh the BLEDevice from the local adapter only."""
        scanner = async_scanner_by_source(hass, service_info.source)
        if isinstance(scanner, BaseHaRemoteScanner):
            return
        device.set_ble_device(service_info.device)

    entry.async_on_unload(
        async_register_callback(
            hass,
            _async_update_ble_device,
            BluetoothCallbackMatcher(address=address, connectable=True),
            BluetoothScanningMode.PASSIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RyseConfigEntry) -> bool:
    """Unload a RYSE config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.unpair()
    return unload_ok
