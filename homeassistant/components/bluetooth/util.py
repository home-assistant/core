"""The bluetooth integration utilities."""
from __future__ import annotations

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bluetooth_adapters import BluetoothAdapters
from bluetooth_auto_recovery import recover_adapter

from homeassistant.core import callback
from homeassistant.util.dt import monotonic_time_coarse

from .models import BluetoothServiceInfoBleak
from .storage import BluetoothStorage


@callback
def async_load_history_from_system(
    adapters: BluetoothAdapters, storage: BluetoothStorage
) -> dict[str, BluetoothServiceInfoBleak]:
    """Load the device and advertisement_data history if available on the current system."""
    now_monotonic = monotonic_time_coarse()
    loaded_history: dict[str, BluetoothServiceInfoBleak] = {}

    # Restore local adapters
    for address, history in adapters.history.items():
        device = history.device
        advertisement_data = history.advertisement_data

        if (
            existing := loaded_history.get(address)
        ) and advertisement_data.rssi < existing.rssi:
            continue

        loaded_history[
            address
        ] = bluetooth_service_info_bleak_from_device_and_advertisement_data(
            device, advertisement_data, history.source, now_monotonic, True
        )

    # Restore remote adapters
    for scanner in storage.scanners():
        if not (adv_history := storage.async_get_advertisement_history(scanner)):
            continue

        connectable = adv_history.connectable
        discovered_device_timestamps = adv_history.discovered_device_timestamps
        for (
            address,
            device_adv,
        ) in adv_history.discovered_device_advertisement_datas.items():
            advertisement_data = device_adv[1]
            if (
                existing := loaded_history.get(address)
            ) and advertisement_data.rssi < existing.rssi:
                continue
            loaded_history[
                address
            ] = bluetooth_service_info_bleak_from_device_and_advertisement_data(
                device_adv[0],
                advertisement_data,
                scanner,
                discovered_device_timestamps[address],
                connectable,
            )

    return loaded_history


def bluetooth_service_info_bleak_from_device_and_advertisement_data(
    device: BLEDevice,
    advertisement_data: AdvertisementData,
    source: str,
    time: float,
    connectable: bool,
) -> BluetoothServiceInfoBleak:
    """Create a BluetoothServiceInfoBleak from a device and advertisement_data."""
    return BluetoothServiceInfoBleak(
        name=advertisement_data.local_name or device.name or device.address,
        address=device.address,
        rssi=advertisement_data.rssi,
        manufacturer_data=advertisement_data.manufacturer_data,
        service_data=advertisement_data.service_data,
        service_uuids=advertisement_data.service_uuids,
        source=source,
        device=device,
        advertisement=advertisement_data,
        connectable=connectable,
        time=time,
    )


async def async_reset_adapter(adapter: str | None) -> bool | None:
    """Reset the adapter."""
    if adapter and adapter.startswith("hci"):
        adapter_id = int(adapter[3:])
        return await recover_adapter(adapter_id)
    return False
