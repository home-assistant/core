"""Support for displaying IPs banned by fail2ban."""
from datetime import timedelta
import logging
import os
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_FILE_PATH, CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_JAILS = "jails"

DEFAULT_NAME = "fail2ban"
DEFAULT_LOG = "/var/log/fail2ban.log"

STATE_CURRENT_BANS = "current_bans"
STATE_ALL_BANS = "total_bans"
SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_JAILS): vol.All(cv.ensure_list, vol.Length(min=1)),
        vol.Optional(CONF_FILE_PATH): cv.isfile,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the fail2ban sensor."""
    name = config.get(CONF_NAME)
    jails = config.get(CONF_JAILS)
    log_file = config.get(CONF_FILE_PATH, DEFAULT_LOG)

    device_list = []
    log_parser = BanLogParser(log_file)
    for jail in jails:
        device_list.append(BanSensor(name, jail, log_parser))

    async_add_entities(device_list, True)


class BanSensor(SensorEntity):
    """Implementation of a fail2ban sensor."""

    def __init__(self, name, jail, log_parser):
        """Initialize the sensor."""
        self._name = f"{name} {jail}"
        self.jail = jail
        self.ban_dict = {STATE_CURRENT_BANS: [], STATE_ALL_BANS: []}
        self.last_ban = None
        self.log_parser = log_parser
        self.log_parser.ip_regex[self.jail] = re.compile(
            r"\[{}\]\s*(Ban|Unban) (.*)".format(re.escape(self.jail))
        )
        _LOGGER.debug("Setting up jail %s", self.jail)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the fail2ban sensor."""
        return self.ban_dict

    @property
    def state(self):
        """Return the most recently banned IP Address."""
        return self.last_ban

    def update(self):
        """Update the list of banned ips."""
        self.log_parser.read_log(self.jail)

        if self.log_parser.data:
            for entry in self.log_parser.data:
                _LOGGER.debug(entry)
                current_ip = entry[1]
                if entry[0] == "Ban":
                    if current_ip not in self.ban_dict[STATE_CURRENT_BANS]:
                        self.ban_dict[STATE_CURRENT_BANS].append(current_ip)
                    if current_ip not in self.ban_dict[STATE_ALL_BANS]:
                        self.ban_dict[STATE_ALL_BANS].append(current_ip)
                    if len(self.ban_dict[STATE_ALL_BANS]) > 10:
                        self.ban_dict[STATE_ALL_BANS].pop(0)

                elif (
                    entry[0] == "Unban"
                    and current_ip in self.ban_dict[STATE_CURRENT_BANS]
                ):
                    self.ban_dict[STATE_CURRENT_BANS].remove(current_ip)

        if self.ban_dict[STATE_CURRENT_BANS]:
            self.last_ban = self.ban_dict[STATE_CURRENT_BANS][-1]
        else:
            self.last_ban = "None"


class BanLogParser:
    """Class to parse fail2ban logs."""

    def __init__(self, log_file):
        """Initialize the parser."""
        self.log_file = log_file
        self.data = []
        self.ip_regex = {}

    def read_log(self, jail):
        """Read the fail2ban log and find entries for jail."""
        self.data = []
        try:
            with open(self.log_file, encoding="utf-8") as file_data:
                self.data = self.ip_regex[jail].findall(file_data.read())

        except (IndexError, FileNotFoundError, IsADirectoryError, UnboundLocalError):
            _LOGGER.warning("File not present: %s", os.path.basename(self.log_file))
