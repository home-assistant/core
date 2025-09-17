"""Support for OpenWRT (ubus) routers."""

from __future__ import annotations

import logging
import re

from openwrt.ubus import Ubus
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

CONF_DHCP_SOFTWARE = "dhcp_software"
DEFAULT_DHCP_SOFTWARE = "dnsmasq"
DHCP_SOFTWARES = ["dnsmasq", "odhcpd", "none"]

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE): vol.In(
            DHCP_SOFTWARES
        ),
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> DeviceScanner | None:
    """Validate the configuration and return an ubus scanner."""
    config = config[DEVICE_TRACKER_DOMAIN]

    dhcp_sw = config[CONF_DHCP_SOFTWARE]
    scanner: DeviceScanner
    if dhcp_sw == "dnsmasq":
        scanner = DnsmasqUbusDeviceScanner(config)
    elif dhcp_sw == "odhcpd":
        scanner = OdhcpdUbusDeviceScanner(config)
    else:
        scanner = UbusDeviceScanner(config)

    return scanner if scanner.success_init else None


def _refresh_on_access_denied(func):
    """If remove rebooted, it lost our session so rebuild one and try again."""

    def decorator(self, *args, **kwargs):
        """Wrap the function to refresh session_id on PermissionError."""
        try:
            return func(self, *args, **kwargs)
        except PermissionError:
            _LOGGER.warning(
                "Invalid session detected. Trying to refresh session_id and re-run RPC"
            )
            self.ubus.connect()

            return func(self, *args, **kwargs)

    return decorator


class UbusDeviceScanner(DeviceScanner):
    """Class which queries a wireless router running OpenWrt firmware.

    Adapted from Tomato scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.ssl = config[CONF_SSL]
        self.verify_ssl = config[CONF_VERIFY_SSL]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")
        self.last_results = {}
        self.url = f"{'https' if self.ssl else 'http'}://{self.host}/ubus"

        self.ubus = Ubus(self.url, self.username, self.password, verify=self.verify_ssl)
        self.hostapd = []
        self.mac2attrs = None
        self.success_init = self.ubus.connect() is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def _generate_mac2attrs(self):
        """Return empty MAC to attributes dict. Overridden if DHCP server is set."""
        self.mac2attrs = {}

    @_refresh_on_access_denied
    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2attrs is None:
            self._generate_mac2attrs()
        if self.mac2attrs is None:
            # Generation of mac2attrs dictionary failed
            return None
        attrs = self.mac2attrs.get(device.upper(), None)
        if attrs is None:
            return None
        return attrs.get("name", None)

    #async def async_get_extra_attributes(self, device: str) -> dict[str, str]:
    #    """Return the host to distinguish between multiple routers and the MAC address."""
    #    return {"host": self.host, "mac": device.upper()}

    def get_extra_attributes(self, device: str) -> dict[str, str]:            
        """Return the host (to distinguish between multiple routers), the MAC address and the IP address (or None if we don't know)."""
        if self.mac2attrs is None:
            self._generate_mac2attrs()
        if self.mac2attrs is None:
            # Generation of mac2attrs dictionary failed
            ip = None
        else:
            attrs = self.mac2attrs.get(device.upper(), None)
            ip = None if attrs is None else attrs.get("ip", None)
        return {"host": self.host, "mac": device.upper(), "ip": ip}

    @_refresh_on_access_denied
    def _update_info(self):
        """Ensure the information from the router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.debug("Checking hostapd")

        if not self.hostapd:
            hostapd = self.ubus.get_hostapd()
            self.hostapd.extend(hostapd.keys())

        self.last_results = []
        results = 0
        # for each access point
        for hostapd in self.hostapd:
            if result := self.ubus.get_hostapd_clients(hostapd):
                results = results + 1
                # Check for each device is authorized (valid wpa key)
                for key in result["clients"]:
                    device = result["clients"][key]
                    if device["authorized"]:
                        self.last_results.append(key)

        return bool(results)


class DnsmasqUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the dnsmasq DHCP server."""

    def __init__(self, config):
        """Initialize the scanner."""
        super().__init__(config)
        self.leasefiles = None

    def _generate_mac2attrs(self):
        if self.leasefiles is None:
            if result := self.ubus.get_uci_config("dhcp", "dnsmasq"):
                values = result["values"].values()
                self.leasefiles = [value["leasefile"] for value in values if "leasefile" in value]
            else:
                return

        for i, leasefile in enumerate(self.leasefiles):
            result = self.ubus.file_read(leasefile)
            if result:
                if i == 0: self.mac2attrs = {}
                for line in result["data"].splitlines():
                    hosts = line.split(" ")
                    self.mac2attrs[hosts[1].upper()] = {"name": hosts[3], "ip": hosts[2]}


class OdhcpdUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the odhcp DHCP server."""

    def _generate_mac2attrs(self):
        if result := self.ubus.get_dhcp_method("ipv4leases"):
            self.mac2attrs = {}
            for device in result["device"].values():
                for lease in device["leases"]:
                    mac = lease["mac"]  # mac = aabbccddeeff
                    # Convert it to expected format with colon
                    mac = ":".join(mac[i : i + 2] for i in range(0, len(mac), 2))
                    self.mac2attrs[mac.upper()] = {"name": lease["hostname"], "ip": lease["address"]}
        else:
            # Error, handled in the ubus.get_dhcp_method()
            return
