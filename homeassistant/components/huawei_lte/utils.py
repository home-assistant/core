"""Utilities for the Huawei LTE integration."""
from __future__ import annotations

from huawei_lte_api.Connection import GetResponseType

from homeassistant.helpers.device_registry import format_mac


def get_device_macs(
    device_info: GetResponseType, wlan_settings: GetResponseType
) -> list[str]:
    """Get list of device MAC addresses.

    :param device_info: the device.information structure for the device
    :param wlan_settings: the wlan.multi_basic_settings structure for the device
    """
    macs = [device_info.get("MacAddress1"), device_info.get("MacAddress2")]
    try:
        macs.extend(x.get("WifiMac") for x in wlan_settings["Ssids"]["Ssid"])
    except Exception:  # pylint: disable=broad-except
        # Assume not supported
        pass
    return sorted({format_mac(str(x)) for x in macs if x})
