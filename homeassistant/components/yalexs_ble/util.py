"""The yalexs_ble integration models."""
from __future__ import annotations

from yalexs_ble import local_name_is_unique

from homeassistant.components.bluetooth.match import (
    ADDRESS,
    LOCAL_NAME,
    BluetoothCallbackMatcher,
)


def bluetooth_callback_matcher(
    local_name: str, address: str
) -> BluetoothCallbackMatcher:
    """Return a BluetoothCallbackMatcher for the given local_name and address."""
    if local_name_is_unique(local_name):
        return BluetoothCallbackMatcher({LOCAL_NAME: local_name})
    return BluetoothCallbackMatcher({ADDRESS: address})
