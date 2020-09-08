"""Support for ASUSWRT routers."""
import logging

from aioasuswrt.asuswrt import AsusWrt

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)

from homeassistant.helpers import config_validation as cv

DEFAULT_SSH_PORT = 22
DEFAULT_INTERFACE = "eth0"
DEFAULT_DNSMASQ = "/var/lib/misc"

CONF_DNSMASQ = "dnsmasq"
CONF_INTERFACE = "interface"
CONF_PUB_KEY = "pub_key"
CONF_REQUIRE_IP = "require_ip"
CONF_SENSORS = "sensors"
CONF_SSH_KEY = "ssh_key"
SECRET_GROUP = "Password or SSH Key"

FIRST_RETRY_TIME = 60
MAX_RETRY_TIME = 900

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PROTOCOL, default="ssh"): vol.In(["ssh", "telnet"]),
        vol.Optional(CONF_MODE, default="router"): vol.In(["router", "ap"]),
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
        vol.Optional(CONF_REQUIRE_IP, default=False): cv.boolean,
        vol.Exclusive(CONF_PASSWORD, SECRET_GROUP): cv.string,
        vol.Exclusive(CONF_SSH_KEY, SECRET_GROUP): cv.isfile,
        vol.Exclusive(CONF_PUB_KEY, SECRET_GROUP): cv.isfile,
        vol.Optional(CONF_INTERFACE, default=DEFAULT_INTERFACE): cv.string,
        vol.Optional(CONF_DNSMASQ, default=DEFAULT_DNSMASQ): cv.string,
    }
)


async def async_get_scanner(hass, config):
    """Validate the configuration and return an ASUS-WRT scanner."""
    return AsusWrtDeviceScanner(config[DOMAIN])


class AsusWrtDeviceScanner(DeviceScanner):
    """This class queries a router running ASUSWRT firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = {}
        self.success_init = False
        self.config = config
        self.connection = AsusWrt(
            config[CONF_HOST],
            config[CONF_PORT],
            config[CONF_PROTOCOL] == "telnet",
            config[CONF_USERNAME],
            config.get(CONF_PASSWORD, ""),
            config.get("ssh_key", config.get("pub_key", "")),
            config[CONF_MODE],
            config[CONF_REQUIRE_IP],
            interface=config[CONF_INTERFACE],
            dnsmasq=config[CONF_DNSMASQ],
        )

        self._connect_error = False

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self.async_update_info()
        return list(self.last_results.keys())

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        return self.last_results[device].name

    async def async_get_extra_attributes(self, mac):
        """Return extra attributes to report in the GUI."""
        return {CONF_HOST: self.config[CONF_HOST]}

    async def async_update_info(self):
        """Ensure the information from the ASUSWRT router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("Checking Devices")

        try:
            self.last_results = await self.connection.async_get_connected_devices()
            if self._connect_error:
                self._connect_error = False
                _LOGGER.info("Reconnected to ASUS router for device update")
        except OSError as err:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error(
                    "Error connecting to ASUS router for device update: %s", err
                )
