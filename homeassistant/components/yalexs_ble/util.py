"""The yalexs_ble integration models."""
from __future__ import annotations

import platform

from yalexs_ble import local_name_is_unique

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.components.bluetooth.match import (
    ADDRESS,
    LOCAL_NAME,
    BluetoothCallbackMatcher,
)
from homeassistant.core import HomeAssistant, callback

from .const import DEVICE_TIMEOUT


def bluetooth_callback_matcher(
    local_name: str, address: str
) -> BluetoothCallbackMatcher:
    """Return a BluetoothCallbackMatcher for the given local_name and address."""
    # On MacOS, coreblueooth uses UUIDs for addresses so we must
    # have a unique local_name to match since the system
    # hides the address from us.
    if local_name_is_unique(local_name) and platform.system() == "Darwin":
        return BluetoothCallbackMatcher({LOCAL_NAME: local_name})
    # On every other platform we actually get the mac address
    # which is needed for the older August locks that use the
    # older version of the underlying protocol.
    return BluetoothCallbackMatcher({ADDRESS: address})


@callback
def async_find_existing_service_info(
    hass: HomeAssistant, local_name: str, address: str
) -> BluetoothServiceInfoBleak | None:
    """Return the service info for the given local_name and address."""
    has_unique_local_name = local_name_is_unique(local_name)
    for service_info in async_discovered_service_info(hass):
        device = service_info.device
        if (
            has_unique_local_name and device.name == local_name
        ) or device.address == address:
            return service_info
    return None


async def async_get_service_info(
    hass: HomeAssistant, local_name: str, address: str
) -> BluetoothServiceInfoBleak:
    """Wait for the service info for the given local_name and address."""
    if service_info := async_find_existing_service_info(hass, local_name, address):
        return service_info
    return await async_process_advertisements(
        hass,
        lambda service_info: True,
        bluetooth_callback_matcher(local_name, address),
        BluetoothScanningMode.ACTIVE,
        DEVICE_TIMEOUT,
    )


def short_address(address: str) -> str:
    """Convert a Bluetooth address to a short address."""
    split_address = address.replace("-", ":").split(":")
    return f"{split_address[-2].upper()}{split_address[-1].upper()}"[-4:]


def human_readable_name(name: str | None, local_name: str, address: str) -> str:
    """Return a human readable name for the given name, local_name, and address."""
    return f"{name or local_name} ({short_address(address)})"
