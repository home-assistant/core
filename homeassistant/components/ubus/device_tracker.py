"""Support for OpenWRT (ubus) routers."""
from dataclasses import dataclass
import json
import logging
from typing import Dict, List

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, HTTP_OK
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_DHCP_SOFTWARE = "dhcp_software"
DEFAULT_DHCP_SOFTWARE = "dnsmasq"
DHCP_SOFTWARES = ["dnsmasq", "odhcpd", "none"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE): vol.In(
            DHCP_SOFTWARES
        ),
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return an ubus scanner."""
    dhcp_sw = config[DOMAIN][CONF_DHCP_SOFTWARE]
    if dhcp_sw == "dnsmasq":
        scanner = DnsmasqUbusDeviceScanner(config[DOMAIN])
    elif dhcp_sw == "odhcpd":
        scanner = OdhcpdUbusDeviceScanner(config[DOMAIN])
    else:
        scanner = UbusDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


def _refresh_on_access_denied(func):
    """If remove rebooted, it lost our session so rebuild one and try again."""

    def decorator(self, *args, **kwargs):
        """Wrap the function to refresh session_id on PermissionError."""
        try:
            return func(self, *args, **kwargs)
        except PermissionError:
            _LOGGER.warning(
                "Invalid session detected."
                " Trying to refresh session_id and re-run RPC"
            )
            self.session_id = _get_session_id(self.url, self.username, self.password)

            return func(self, *args, **kwargs)

    return decorator


@dataclass
class _Wlan:
    hostapd: str
    ssid: str


@dataclass
class _Device:
    ssid: str
    host: str


class UbusDeviceScanner(DeviceScanner):
    """
    This class queries a wireless router running OpenWrt firmware.

    Adapted from Tomato scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.last_results: Dict[str, _Device] = {}
        self.url = f"http://{self.host}/ubus"

        self.session_id = _get_session_id(self.url, self.username, self.password)
        self.wlans: [_Wlan] = []
        self.mac2name = None
        self.success_init = self.session_id is not None

    def scan_devices(self) -> List[str]:
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return list(self.last_results.keys())

    def _generate_mac2name(self):
        """Return empty MAC to name dict. Overridden if DHCP server is set."""
        self.mac2name = {}

    @_refresh_on_access_denied
    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            self._generate_mac2name()
        if self.mac2name is None:
            # Generation of mac2name dictionary failed
            return None
        name = self.mac2name.get(device.upper(), None)
        return name

    @_refresh_on_access_denied
    def _update_info(self):
        """Ensure the information from the router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Checking hostapd for host: %s", self.host)

        if not self.wlans:
            hostapd = _req_json_rpc(self.url, self.session_id, "list", "hostapd.*", "")
            for name in hostapd.keys():
                iwinfo = _req_json_rpc(
                    self.url,
                    self.session_id,
                    "call",
                    "iwinfo",
                    "info",
                    device=name.split(".", maxsplit=1)[1],
                )
                self.wlans.append(_Wlan(name, iwinfo.get("ssid", None)))

        self.last_results = {}
        # for each access point
        for wlan in self.wlans:
            result = _req_json_rpc(
                self.url, self.session_id, "call", wlan.hostapd, "get_clients"
            )

            if result:
                # Check for each device is authorized (valid wpa key)
                for key in result["clients"].keys():
                    device = result["clients"][key]
                    if device["authorized"]:
                        self.last_results[key] = _Device(wlan.ssid, self.host)

    def get_extra_attributes(self, device: str) -> dict:
        """
        Get extra attributes of a device.

        Some known extra attributes that may be returned in the device tuple
        include associated router (host) and the name of the connected wlan (ssid).
        """
        found = self.last_results.get(device, None)
        return found.__dict__ if found else None


class DnsmasqUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the dnsmasq DHCP server."""

    def __init__(self, config):
        """Initialize the scanner."""
        super().__init__(config)
        self.leasefile = None

    def _generate_mac2name(self):
        if self.leasefile is None:
            result = _req_json_rpc(
                self.url,
                self.session_id,
                "call",
                "uci",
                "get",
                config="dhcp",
                type="dnsmasq",
            )
            if result:
                values = result["values"].values()
                self.leasefile = next(iter(values))["leasefile"]
            else:
                return

        result = _req_json_rpc(
            self.url, self.session_id, "call", "file", "read", path=self.leasefile
        )
        if result:
            self.mac2name = {}
            for line in result["data"].splitlines():
                hosts = line.split(" ")
                self.mac2name[hosts[1].upper()] = hosts[3]
        else:
            # Error, handled in the _req_json_rpc
            return


class OdhcpdUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the odhcp DHCP server."""

    def _generate_mac2name(self):
        result = _req_json_rpc(self.url, self.session_id, "call", "dhcp", "ipv4leases")
        if result:
            self.mac2name = {}
            for device in result["device"].values():
                for lease in device["leases"]:
                    mac = lease["mac"]  # mac = aabbccddeeff
                    # Convert it to expected format with colon
                    mac = ":".join(mac[i : i + 2] for i in range(0, len(mac), 2))
                    self.mac2name[mac.upper()] = lease["hostname"]
        else:
            # Error, handled in the _req_json_rpc
            return


def _req_json_rpc(url, session_id, rpcmethod, subsystem, method, **params):
    """Perform one JSON RPC operation."""
    data = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": rpcmethod,
            "params": [session_id, subsystem, method, params],
        }
    )

    try:
        res = requests.post(url, data=data, timeout=5)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return

    if res.status_code == HTTP_OK:
        response = res.json()
        if "error" in response:
            if (
                "message" in response["error"]
                and response["error"]["message"] == "Access denied"
            ):
                raise PermissionError(response["error"]["message"])
            raise HomeAssistantError(response["error"]["message"])

        if rpcmethod == "call":
            if response["result"][0] == 6:
                # 6 = UBUS_STATUS_PERMISSION_DENIED
                _LOGGER.error(
                    "Permission denied. Please check username/password and acl/user-permissions"
                )
                return
            try:
                return response["result"][1]
            except IndexError:
                return
        else:
            return response["result"]


def _get_session_id(url, username, password):
    """Get the authentication token for the given host+username+password."""
    res = _req_json_rpc(
        url,
        "00000000000000000000000000000000",
        "call",
        "session",
        "login",
        username=username,
        password=password,
    )
    if res:
        return res["ubus_rpc_session"]
