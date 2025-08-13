"""Diagnostics support for Huawei LTE."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

ENTRY_FIELDS_DATA_TO_REDACT = {
    "mac",
    "username",
    "password",
}
DEVICE_INFORMATION_DATA_TO_REDACT = {
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
}
DEVICE_SIGNAL_DATA_TO_REDACT = {
    "pci",
    "cell_id",
    "enodeb_id",
    "rac",
    "lac",
    "tac",
    "nei_cellid",
    "plmn",
    "bsic",
}
MONITORING_STATUS_DATA_TO_REDACT = {
    "PrimaryDns",
    "SecondaryDns",
    "PrimaryIPv6Dns",
    "SecondaryIPv6Dns",
}
NET_CURRENT_PLMN_DATA_TO_REDACT = {
    "net_current_plmn",
}
LAN_HOST_INFO_DATA_TO_REDACT = {
    "lan_host_info",
}
WLAN_WIFI_GUEST_NETWORK_SWITCH_DATA_TO_REDACT = {
    "Ssid",
    "WifiSsid",
}
WLAN_MULTI_BASIC_SETTINGS_DATA_TO_REDACT = {
    "WifiMac",
}
TO_REDACT = {
    *ENTRY_FIELDS_DATA_TO_REDACT,
    *DEVICE_INFORMATION_DATA_TO_REDACT,
    *DEVICE_SIGNAL_DATA_TO_REDACT,
    *MONITORING_STATUS_DATA_TO_REDACT,
    *NET_CURRENT_PLMN_DATA_TO_REDACT,
    *LAN_HOST_INFO_DATA_TO_REDACT,
    *WLAN_WIFI_GUEST_NETWORK_SWITCH_DATA_TO_REDACT,
    *WLAN_MULTI_BASIC_SETTINGS_DATA_TO_REDACT,
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
