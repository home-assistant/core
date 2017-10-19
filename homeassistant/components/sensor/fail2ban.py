"""
Support for displaying IPs banned by fail2ban.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fail2ban/
"""
import os
import asyncio
from datetime import timedelta
import logging

import voluptuous as voluptuous

import homeassistant.helper.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_SCAN_INTERVAL, CONF_FILE_PATH
)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_JAILS = 'jails'

DEFAULT_NAME = 'fail2ban'
DEFAULT_LOG = '/var/log/syslog'
DEFAULT_SCAN_INTERVAL = 120

STATE_BANS = 'current_bans'
STATE_COUNT = 'total_bans'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_JAILS, default=[]): 
        vol.All(cv.ensure_list, vol.Length(min=1)),
    vol.Optional(CONF_FILE_PATH, default=DEFAULT_LOG): cv.isfile,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL,default=DEFAULT_SCAN_INTERVAL): 
        cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the fail2ban sensor."""
    name = config.get(CONF_NAME)
    jails = config.get(CONF_JAILS)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    log_file = config.get(CONF_FILE_PATH)

    device_list = []
    for jail in jails:
        device_list.append(BanSensor(name, jail, scan_interval, log_file))

    async_add_devices(device_list, True)


class BanSensor(Entity):
    """Implementation of a fail2ban sensor."""

    def __init__(self, name, jail, scan_interval, log_file):
        """Initialize the sensor."""
        self._name = name
        self.jail = jail
        self.interval = timedelta(seconds=scan_interval)
        self.log_file = log_file
        self.ban_dict = {STATE_BANS: [], STATE_COUNT: 0}
        self.last_ban = None
        self.last_update = dt_util.now()

    @property
    def state_attributes(self):
        """Return the state attributes of the fail2ban sensor."""
        return self.ban_dict

    @property
    def state(self):
        """Return the most recently banned IP Address."""
        return self.last_ban

    def update(self):
        """Update the list of banned ips."""
        boundary = dt_util.now() - self.interval
        jail_data = list()
        if boundary > self.last_update:
            _LOGGER.info("Checking log for ip bans in %s", self.jail)
            try:
                with open(self.log_file, 'r', encoding='utf-8') as file_data:
                    for line in file_data:
                        if self.jail and 'fail2ban.action' in line:
                            jail_data.append(line)
            except (IndexError, FileNotFoundError, IsADirectoryError,
                    UnboundLocalError):
                _LOGGER.warning("File or data not present at the moment: %s",
                                os.path.basename(self._file_path))
                return
        if jail_data:
            for entry in jail_data:
                _LOGGER.debug(entry)
                split_entry = entry.split()
                if 'Ban' in split_entry:
                    ip_index = split_entry.index('Ban') + 1
                    this_ban = split_entry[ip_index]
                    if this_ban not in self.ban_dict[STATE_BANS]:
                        self.last_ban = this_ban
                        self.ban_dict[STATE_BANS].append(self.last_ban)
                        self.ban_dict[STATE_COUNT] += 1
                elif 'Unban' in split_entry:
                    ip_index = split_entry.index('Unban') + 1
                    this_unban = split_entry[ip_index]
                    if this_unban in self.ban_dict[STATE_BANS]:
                        self.ban_dict[STATE_BANS].remove(this_unban)
        else:
            self.last_ban = 'None'
    