"""Utilities for the Huawei LTE integration."""
from __future__ import annotations

from contextlib import suppress

from huawei_lte_api.Session import GetResponseType

from homeassistant.helpers.device_registry import format_mac


def get_device_macs(
    device_info: GetResponseType, wlan_settings: GetResponseType
) -> list[str]:
    """Get list of device MAC addresses.

    :param device_info: the device.information structure for the device
    :param wlan_settings: the wlan.multi_basic_settings structure for the device
    """
    macs = [
        device_info.get(x)
        for x in ("MacAddress1", "MacAddress2", "WifiMacAddrWl0", "WifiMacAddrWl1")
    ]
    # Assume not supported when exception is thrown
    with suppress(Exception):  # pylint: disable=broad-except
        macs.extend(x.get("WifiMac") for x in wlan_settings["Ssids"]["Ssid"])

    return sorted({format_mac(str(x)) for x in macs if x})
