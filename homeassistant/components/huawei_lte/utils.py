"""Utilities for the Huawei LTE integration."""
from __future__ import annotations

from contextlib import suppress
import re
from urllib.parse import urlparse
import warnings

from huawei_lte_api.Session import GetResponseType
import requests
from urllib3.exceptions import InsecureRequestWarning

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
    with suppress(Exception):
        macs.extend(x.get("WifiMac") for x in wlan_settings["Ssids"]["Ssid"])

    return sorted({format_mac(str(x)) for x in macs if x})


def non_verifying_requests_session(url: str) -> requests.Session:
    """Get requests.Session that does not verify HTTPS, filter warnings about it."""
    parsed_url = urlparse(url)
    assert parsed_url.hostname
    requests_session = requests.Session()
    requests_session.verify = False
    warnings.filterwarnings(
        "ignore",
        message=rf"^.*\b{re.escape(parsed_url.hostname)}\b",
        category=InsecureRequestWarning,
        module=r"^urllib3\.connectionpool$",
    )
    return requests_session
