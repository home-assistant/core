"""The bluetooth integration utilities."""

from __future__ import annotations

from bluetooth_adapters import (
    ADAPTER_ADDRESS,
    ADAPTER_MANUFACTURER,
    ADAPTER_PRODUCT,
    AdapterDetails,
    BluetoothAdapters,
    adapter_unique_name,
)
from bluetooth_data_tools import monotonic_time_coarse
from habluetooth import get_manager

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .models import BluetoothServiceInfoBleak
from .storage import BluetoothStorage


class InvalidConfigEntryID(HomeAssistantError):
    """Invalid config entry id."""


class InvalidSource(HomeAssistantError):
    """Invalid source."""


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
    adapter_to_source_address = {
        adapter: details[ADAPTER_ADDRESS]
        for adapter, details in adapters.adapters.items()
    }

    # Restore local adapters
    for address, history in adapters.history.items():
        if (
            not (existing_all := connectable_loaded_history.get(address))
            or history.advertisement_data.rssi > existing_all.rssi
        ):
            connectable_loaded_history[address] = all_loaded_history[address] = (
                BluetoothServiceInfoBleak.from_device_and_advertisement_data(
                    history.device,
                    history.advertisement_data,
                    # history.source is really the adapter name
                    # for historical compatibility since BlueZ
                    # does not know the MAC address of the adapter
                    # so we need to convert it to the source address (MAC)
                    adapter_to_source_address.get(history.source, history.source),
                    now_monotonic,
                    True,
                )
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


@callback
def adapter_title(adapter: str, details: AdapterDetails) -> str:
    """Return the adapter title."""
    unique_name = adapter_unique_name(adapter, details[ADAPTER_ADDRESS])
    model = details.get(ADAPTER_PRODUCT, "Unknown")
    manufacturer = details[ADAPTER_MANUFACTURER] or "Unknown"
    return f"{manufacturer} {model} ({unique_name})"


def config_entry_id_to_source(hass: HomeAssistant, config_entry_id: str) -> str:
    """Convert a config entry id to a source."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise InvalidConfigEntryID(f"Config entry {config_entry_id} not found")
    source = entry.unique_id
    assert source is not None
    if not get_manager().async_scanner_by_source(source):
        raise InvalidSource(f"Source {source} not found")
    return source
