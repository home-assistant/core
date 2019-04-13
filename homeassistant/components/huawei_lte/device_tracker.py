"""Support for device tracking of Huawei LTE routers."""
from typing import Any, Dict, List, Optional

import attr
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DeviceScanner,
)
from homeassistant.const import CONF_URL
from ..huawei_lte import DATA_KEY, RouterData

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_URL): cv.url,
})

HOSTS_PATH = "wlan_host_list.Hosts"


def get_scanner(hass, config):
    """Get a Huawei LTE router scanner."""
    data = hass.data[DATA_KEY].get_data(config)
    data.subscribe(HOSTS_PATH)
    return HuaweiLteScanner(data)


@attr.s
class HuaweiLteScanner(DeviceScanner):
    """Huawei LTE router scanner."""

    data = attr.ib(type=RouterData)

    _hosts = attr.ib(init=False, factory=dict)

    def scan_devices(self) -> List[str]:
        """Scan for devices."""
        self.data.update()
        self._hosts = {
            x["MacAddress"]: x
            for x in self.data[HOSTS_PATH + ".Host"]
            if x.get("MacAddress")
        }
        return list(self._hosts)

    def get_device_name(self, device: str) -> Optional[str]:
        """Get name for a device."""
        host = self._hosts.get(device)
        return host.get("HostName") or None if host else None

    def get_extra_attributes(self, device: str) -> Dict[str, Any]:
        """
        Get extra attributes of a device.

        Some known extra attributes that may be returned in the dict
        include MacAddress (MAC address), ID (client ID), IpAddress
        (IP address), AssociatedSsid (associated SSID), AssociatedTime
        (associated time in seconds), and HostName (host name).
        """
        return self._hosts.get(device) or {}
