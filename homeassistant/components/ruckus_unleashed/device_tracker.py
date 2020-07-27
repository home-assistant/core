"""Support for Ruckus Unleashed APs."""
import logging

import pexpect
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD, default=""): cv.string,
        }
    )
)

RUCKUS_PROMPT = "ruckus>"
RUCKUS_PROMPT_ENABLE = "ruckus#"
RUCKUS_MAC_ADDRESS = "Mac Address="


def get_scanner(hass, config):
    """Validate the configuration and return a Unleashed scanner."""
    scanner = UnleashedDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class UnleashedDeviceScanner(DeviceScanner):
    """This class queries a wireless router running Unleashed IOS firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.port = config.get(CONF_PORT)
        self.password = config[CONF_PASSWORD]

        self.last_results = {}

        self.success_init = self._update_info()
        _LOGGER.info("ruckus_unleashed scanner initialized")

    def get_device_name(self, device):
        """Get the firmware doesn't save the name of the wireless device."""
        return None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

    def _update_info(self):
        """
        Ensure the information from the Unleashed APs is up to date.

        Returns boolean if scanning successful.
        """
        string_result = self._get_wlan_clients()

        if string_result:
            lines = string_result.splitlines()
            mac_addresses = [
                line.replace(RUCKUS_MAC_ADDRESS, "").strip()
                for line in lines
                if RUCKUS_MAC_ADDRESS in line
            ]

            self.last_results = mac_addresses
            return True

        return False

    def _get_wlan_clients(self):
        """Open connection to the router and get the list of clients."""

        try:
            child = pexpect.spawn(f"ssh {self.host}")
            child.expect("Please login:")
            child.sendline(self.username)
            child.expect("Password:")
            child.sendline(self.password)
            child.expect(RUCKUS_PROMPT)
            child.sendline("enable")
            child.expect(RUCKUS_PROMPT_ENABLE)
            child.sendline("show current-active-clients all")
            child.expect(RUCKUS_PROMPT_ENABLE)
            child.close()

            return child.before.decode("utf-8")
        except pexpect.ExceptionPexpect as ex:
            _LOGGER.error("Failed to retrieve WLAN client list")
            _LOGGER.error(ex)

        return None
