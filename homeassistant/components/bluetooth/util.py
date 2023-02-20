"""The bluetooth integration utilities."""
from __future__ import annotations

from bluetooth_adapters import BluetoothAdapters
from bluetooth_auto_recovery import recover_adapter

from homeassistant.core import callback
from homeassistant.util.dt import monotonic_time_coarse

from .models import BluetoothServiceInfoBleak
from .storage import BluetoothStorage


@callback
def async_load_history_from_system(
    adapters: BluetoothAdapters, storage: BluetoothStorage
) -> tuple[dict[str, BluetoothServiceInfoBleak], dict[str, BluetoothServiceInfoBleak]]:
    """Load the device and advertisement_data history.

    Only loads if available on the current system.
    """
    now_monotonic = monotonic_time_coarse()
    connectable_loaded_history: dict[str, BluetoothServiceInfoBleak] = {}
    all_loaded_history: dict[str, BluetoothServiceInfoBleak] = {}

    # Restore local adapters
    for address, history in adapters.history.items():
        if (
            not (existing_all := connectable_loaded_history.get(address))
            or history.advertisement_data.rssi > existing_all.rssi
        ):
            connectable_loaded_history[address] = all_loaded_history[
                address
            ] = BluetoothServiceInfoBleak.from_device_and_advertisement_data(
                history.device,
                history.advertisement_data,
                history.source,
                now_monotonic,
                True,
            )

    # Restore remote adapters
    for scanner in storage.scanners():
        if not (adv_history := storage.async_get_advertisement_history(scanner)):
            continue

        connectable = adv_history.connectable
        discovered_device_timestamps = adv_history.discovered_device_timestamps
        for (
            address,
            (device, advertisement_data),
        ) in adv_history.discovered_device_advertisement_datas.items():
            service_info = BluetoothServiceInfoBleak.from_device_and_advertisement_data(
                device,
                advertisement_data,
                scanner,
                discovered_device_timestamps[address],
                connectable,
            )
            if (
                not (existing_all := all_loaded_history.get(address))
                or service_info.rssi > existing_all.rssi
            ):
                all_loaded_history[address] = service_info
            if connectable and (
                not (existing_connectable := connectable_loaded_history.get(address))
                or service_info.rssi > existing_connectable.rssi
            ):
                connectable_loaded_history[address] = service_info

    return all_loaded_history, connectable_loaded_history


async def async_reset_adapter(adapter: str | None, mac_address: str) -> bool | None:
    """Reset the adapter."""
    if adapter and adapter.startswith("hci"):
        adapter_id = int(adapter[3:])
        return await recover_adapter(adapter_id, mac_address)
    return False
