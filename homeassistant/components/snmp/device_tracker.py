"""Support for fetching WiFi associations through SNMP."""
from __future__ import annotations

import binascii
import logging

from pysnmp.entity import config as cfg
from pysnmp.entity.rfc3413.oneliner import cmdgen
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_COMMUNITY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BASEOID): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Inclusive(CONF_AUTH_KEY, "keys"): cv.string,
        vol.Inclusive(CONF_PRIV_KEY, "keys"): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> SnmpScanner | None:
    """Validate the configuration and return an SNMP scanner."""
    scanner = SnmpScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SnmpScanner(DeviceScanner):
    """Queries any SNMP capable Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""

        self.snmp = cmdgen.CommandGenerator()

        self.host = cmdgen.UdpTransportTarget((config[CONF_HOST], 161))
        if CONF_AUTH_KEY not in config or CONF_PRIV_KEY not in config:
            self.auth = cmdgen.CommunityData(config[CONF_COMMUNITY])
        else:
            self.auth = cmdgen.UsmUserData(
                config[CONF_COMMUNITY],
                config[CONF_AUTH_KEY],
                config[CONF_PRIV_KEY],
                authProtocol=cfg.usmHMACSHAAuthProtocol,
                privProtocol=cfg.usmAesCfb128Protocol,
            )
        self.baseoid = cmdgen.MibVariable(config[CONF_BASEOID])
        self.last_results = []

        # Test the router is accessible
        data = self.get_snmp_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.last_results if client.get("mac")]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # We have no names
        return None

    def _update_info(self):
        """Ensure the information from the device is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        if not (data := self.get_snmp_data()):
            return False

        self.last_results = data
        return True

    def get_snmp_data(self):
        """Fetch MAC addresses from access point via SNMP."""
        devices = []

        errindication, errstatus, errindex, restable = self.snmp.nextCmd(
            self.auth, self.host, self.baseoid
        )

        if errindication:
            _LOGGER.error("SNMPLIB error: %s", errindication)
            return
        if errstatus:
            _LOGGER.error(
                "SNMP error: %s at %s",
                errstatus.prettyPrint(),
                errindex and restable[int(errindex) - 1][0] or "?",
            )
            return

        for resrow in restable:
            for _, val in resrow:
                try:
                    mac = binascii.hexlify(val.asOctets()).decode("utf-8")
                except AttributeError:
                    continue
                _LOGGER.debug("Found MAC address: %s", mac)
                mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
                devices.append({"mac": mac})
        return devices
