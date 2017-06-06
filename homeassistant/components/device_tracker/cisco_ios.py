"""
Support for Cisco IOS Routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.cisco_ios/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, \
    CONF_PORT
from homeassistant.util import Throttle

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pexpect==4.0.1']

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=''): cv.string,
        vol.Optional(CONF_PORT): cv.port,
    })
)


def get_scanner(hass, config):
    """Validate the configuration and return a Cisco scanner."""
    scanner = CiscoDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class CiscoDeviceScanner(DeviceScanner):
    """This class queries a wireless router running Cisco IOS firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.port = config.get(CONF_PORT)
        self.password = config.get(CONF_PASSWORD)

        self.last_results = {}

        self.success_init = self._update_info()
        _LOGGER.info('cisco_ios scanner initialized')

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """Get the firmware doesn't save the name of the wireless device."""
        return None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Ensure the information from the Cisco router is up to date.

        Returns boolean if scanning successful.
        """
        string_result = self._get_arp_data()

        if string_result:
            self.last_results = []
            last_results = []

            lines_result = string_result.splitlines()

            # Remove the first two lines, as they contains the arp command
            # and the arp table titles e.g.
            # show ip arp
            # Protocol  Address | Age (min) | Hardware Addr | Type | Interface
            lines_result = lines_result[2:]

            for line in lines_result:
                if len(line.split()) is 6:
                    parts = line.split()
                    if len(parts) != 6:
                        continue

                    # ['Internet', '10.10.11.1', '-', '0027.d32d.0123', 'ARPA',
                    # 'GigabitEthernet0']
                    age = parts[2]
                    hw_addr = parts[3]

                    if age != "-":
                        mac = _parse_cisco_mac_address(hw_addr)
                        age = int(age)
                        if age < 1:
                            last_results.append(mac)

            self.last_results = last_results
            return True

        return False

    def _get_arp_data(self):
        """Open connection to the router and get arp entries."""
        from pexpect import pxssh
        import re

        try:
            cisco_ssh = pxssh.pxssh()
            cisco_ssh.login(self.host, self.username, self.password,
                            port=self.port, auto_prompt_reset=False)

            # Find the hostname
            initial_line = cisco_ssh.before.decode('utf-8').splitlines()
            router_hostname = initial_line[len(initial_line) - 1]
            router_hostname += "#"
            # Set the discovered hostname as prompt
            regex_expression = ('(?i)^%s' % router_hostname).encode()
            cisco_ssh.PROMPT = re.compile(regex_expression, re.MULTILINE)
            # Allow full arp table to print at once
            cisco_ssh.sendline("terminal length 0")
            cisco_ssh.prompt(1)

            cisco_ssh.sendline("show ip arp")
            cisco_ssh.prompt(1)

            devices_result = cisco_ssh.before

            return devices_result.decode('utf-8')
        except pxssh.ExceptionPxssh as px_e:
            _LOGGER.error("pxssh failed on login")
            _LOGGER.error(px_e)

        return None


def _parse_cisco_mac_address(cisco_hardware_addr):
    """
    Parse a Cisco formatted HW address to normal MAC.

    e.g. convert
    001d.ec02.07ab

    to:
    00:1D:EC:02:07:AB

    Takes in cisco_hwaddr: HWAddr String from Cisco ARP table
    Returns a regular standard MAC address
    """
    cisco_hardware_addr = cisco_hardware_addr.replace('.', '')
    blocks = [cisco_hardware_addr[x:x + 2]
              for x in range(0, len(cisco_hardware_addr), 2)]

    return ':'.join(blocks).upper()
