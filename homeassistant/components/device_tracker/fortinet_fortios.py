"""
Support for Fortigate/FortiWifi Routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.fortios/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, \
    CONF_PORT
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

CONF_VDOM = 'vdom'

REQUIREMENTS = ['pexpect==4.0.1']

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=''): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_VDOM): cv.string,
    })
)

DEFAULT_DEVICE_IDLE_TIMEOUT = 300


def get_scanner(hass, config):
    """Validate the configuration and return a Fortinet scanner."""
    scanner = FortinetDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class FortinetDeviceScanner(DeviceScanner):
    """This class queries a router running Fortinet fortios firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config.get(CONF_HOST)
        self.username = config.get(CONF_USERNAME)
        self.port = config.get(CONF_PORT)
        self.password = config.get(CONF_PASSWORD)
        self.vdom = config.get(CONF_VDOM)

        self.last_results = {}

        self.success_init = self._update_info()
        _LOGGER.info('fortinet_fortios scanner initialized')

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """Get the firmware doesn't save the name of the wireless device."""
        return None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

    def _update_info(self):
        """
        Returns boolean if scanning successful.
        """
        import datetime

        max_age = self._get_device_idle_timeout()
        string_result = self._get_device_data()

        if string_result:
            self.last_results = {}
            last_results = {}

            lines_result = string_result.splitlines()

            for line in lines_result:
                line = line.strip()
                parts = line.split()

                _LOGGER.debug("line %s", line)

                if line.startswith('vd '):
                    hw_addr = parts[2].upper()
                    ip_addr = None
                elif line.startswith('created '):
                    seen = int(parts[5].replace('s', ''))
                    last_seen = datetime.datetime.now()
                    - datetime.timedelta(seconds=seen)
                elif line.startswith('ip '):
                    ip_addr = parts[1]
                elif line.startswith('host '):
                    if " src configured" in line:
                        devcfg = True
                    else:
                        devcfg = False

                    _LOGGER.info("found %s/%s age %s<?%s cfg %s",
                                 ip_addr, hw_addr, seen, max_age,
                                 devcfg)

                    if devcfg is True:
                        start_index = line.index("'") + 1
                        end_index = line.rindex("'")

                        host = line[start_index:end_index]
                        dev_id = slugify(host)

                        _LOGGER.debug("host %s", host)

                        if hw_addr is not None:
                            _LOGGER.debug("add the device")

                            last_results[hw_addr] = {
                                'id': dev_id,
                                'name': host,
                                'last_seen': last_seen,
                                'ip': ip_addr,
                                'mac': hw_addr
                            }

            self.last_results = last_results

            return True

        return False

    def _login_to_router(self):
        from pexpect import pxssh
        import re

        try:
            fortinet_ssh = pxssh.pxssh()
            fortinet_ssh.login(self.host, self.username, self.password,
                                port=self.port, auto_prompt_reset=False)

            initial_line = fortinet_ssh.before.decode('utf-8').splitlines()
            router_hostname = initial_line[len(initial_line) - 1]
            router_hostname += "#"
            regex_expression = ('(?i)^%s' % router_hostname).encode()
            fortinet_ssh.PROMPT = re.compile(regex_expression, re.MULTILINE)

            return fortinet_ssh
        except pxssh.ExceptionPxssh as px_e:
            _LOGGER.error("pxssh failed on login")
            _LOGGER.error(px_e)

        return None

    def _get_device_idle_timeout(self):
        """Gets the configured device_idle_timeout or returns the default."""

        fortinet_ssh = self._login_to_router()

        if fortinet_ssh is not None:
            fortinet_ssh.sendline("co sys glo")
            fortinet_ssh.prompt(1)

            fortinet_ssh.sendline("sh fu | grep device-idle-timeout")
            fortinet_ssh.prompt(1)

            conf_result = fortinet_ssh.before.decode('utf-8')
            _LOGGER.debug("config output '%s'", conf_result)

            lines = conf_result.splitlines()
            conf_result = lines[2].strip()

            parts = conf_result.split()
            max_age = int(parts[2])

            _LOGGER.info("device_idle_timeout %s", max_age)

            fortinet_ssh.sendline('end')
            fortinet_ssh.prompt()

            fortinet_ssh.sendline('exit')

            return max_age

        return DEFAULT_DEVICE_IDLE_TIMEOUT

    def _get_device_data(self):
        """Open connection to the router and get device entries."""

        fortinet_ssh = self._login_to_router()

        if fortinet_ssh is not None:
            # Set VDOM (optional)
            if self.vdom is not None:
                _LOGGER.info('vdom %s', self.vdom)
                fortinet_ssh.sendline("co vdom")
                fortinet_ssh.prompt(1)

                fortinet_ssh.sendline("edit '" + self.vdom + "'")
                fortinet_ssh.prompt(1)

            fortinet_ssh.sendline("di user device list")
            fortinet_ssh.prompt(1)

            devices_result = fortinet_ssh.before.decode('utf-8')
            _LOGGER.debug(devices_result)

            if self.vdom is not None:
                fortinet_ssh.sendline('end')
                fortinet_ssh.prompt(1)

                fortinet_ssh.sendline('exit')

            return devices_result

        return None
