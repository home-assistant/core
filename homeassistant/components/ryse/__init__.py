"""The RYSE integration."""

from bleak import BleakError
from ryseble.device import RyseBLEDevice

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

type RyseConfigEntry = ConfigEntry[RyseBLEDevice]

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: RyseConfigEntry) -> bool:
    """Set up RYSE."""
    address = entry.unique_id
    assert address is not None

    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find RYSE device with address {address}")

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
        """Follow the device as it moves between adapters and Bluetooth proxies."""
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
