"""The yalexs_ble integration models."""
from __future__ import annotations

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

from .const import DISCOVERY_TIMEOUT


def bluetooth_callback_matcher(
    local_name: str, address: str
) -> BluetoothCallbackMatcher:
    """Return a BluetoothCallbackMatcher for the given local_name and address."""
    if local_name_is_unique(local_name):
        return BluetoothCallbackMatcher({LOCAL_NAME: local_name})
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
        DISCOVERY_TIMEOUT,
    )
