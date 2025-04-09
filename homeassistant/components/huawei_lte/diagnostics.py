"""Diagnostics support for Huawei LTE."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    # Entry fields
    "mac",
    "username",
    "password",
    # device_information
    "SerialNumber",
    "Imei",
    "Imsi",
    "Iccid",
    "Msisdn",
    "MacAddress1",
    "MacAddress2",
    "WanIPAddress",
    "wan_dns_address",
    "WanIPv6Address",
    "wan_ipv6_dns_address",
    "Mccmnc",
    "WifiMacAddrWl0",
    "WifiMacAddrWl1",
    # device_signal
    "pci",
    "cell_id",
    "rac",
    "lac",
    "tac",
    "nei_cellid",
    "plmn",
    "bsic",
    # monitoring_status
    "PrimaryDns",
    "SecondaryDns",
    "PrimaryIPv6Dns",
    "SecondaryIPv6Dns",
    # net_current_plmn
    "net_current_plmn",
    # lan_host_info
    "lan_host_info",
    # wlan_wifi_guest_network_switch
    "Ssid",
    "WifiSsid",
    # wlan.multi_basic_settings
    "WifiMac",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "entry": entry.data,
            "router": hass.data[DOMAIN].routers[entry.entry_id].data,
        },
        TO_REDACT,
    )
