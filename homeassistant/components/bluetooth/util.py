"""The bluetooth integration utilities."""
from __future__ import annotations

from bluetooth_adapters import BluetoothAdapters
from bluetooth_auto_recovery import recover_adapter

from homeassistant.core import callback
from homeassistant.util.dt import monotonic_time_coarse

from .models import BluetoothServiceInfoBleak


@callback
def async_load_history_from_system(
    adapters: BluetoothAdapters,
) -> dict[str, BluetoothServiceInfoBleak]:
    """Load the device and advertisement_data history if available on the current system."""
    now = monotonic_time_coarse()
    return {
        address: BluetoothServiceInfoBleak(
            name=history.advertisement_data.local_name
            or history.device.name
            or history.device.address,
            address=history.device.address,
            rssi=history.advertisement_data.rssi,
            manufacturer_data=history.advertisement_data.manufacturer_data,
            service_data=history.advertisement_data.service_data,
            service_uuids=history.advertisement_data.service_uuids,
            source=history.source,
            device=history.device,
            advertisement=history.advertisement_data,
            connectable=False,
            time=now,
        )
        for address, history in adapters.history.items()
    }


async def async_reset_adapter(adapter: str | None) -> bool | None:
    """Reset the adapter."""
    if adapter and adapter.startswith("hci"):
        adapter_id = int(adapter[3:])
        return await recover_adapter(adapter_id)
    return False
