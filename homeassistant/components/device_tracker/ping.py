"""
Support for detect network host with ping.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ping/

device_tracker:
  - platform: ping
    count: 2
    hosts:
      - 192.168.2.10
      - 192.168.2.25
"""

import logging
import subprocess
import re
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DEFAULT_SCAN_INTERVAL)
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant import util
from homeassistant import const
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = []

_LOGGER = logging.getLogger(__name__)

CONF_PING_COUNT = 'count'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(const.CONF_HOSTS): cv.ensure_list,
    vol.Optional(CONF_PING_COUNT, default=2): cv.positive_int,
})


class Host:
    """Host with ping and mac detection"""

    def __init__(self, ip_address, hass, config):
        self.hass = hass
        self.ip_address = ip_address
        self.mac = ''
        self.dev_id = ''
        self._count = config[CONF_PING_COUNT]
        self._ping_cmd = ['ping', '-q', '-W1',
                          '-c{}'.format(self._count), self.ip_address]
        self._arp_cmd = ['arp', '-n', self.ip_address]

    def _get_mac(self):
        """get the MAC address from ip_address"""
        arp = subprocess.Popen(self._arp_cmd, stdout=subprocess.PIPE)
        out, _ = arp.communicate()
        match = re.search(
            r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})', str(out))
        if match:
            return match.group(0)
        _LOGGER.warning('No MAC address found for %s', self.ip_address)
        return ''

    def set_mac(self, mac):
        """set mac device if valid"""
        if not mac:
            return
        self.mac = mac
        self.dev_id = 'ping_' + util.slugify(self.mac)

    def ping(self):
        """make ping and return True if success"""
        pinger = subprocess.Popen(self._ping_cmd, stdout=subprocess.PIPE)
        try:
            pinger.communicate()
            return pinger.returncode == 0
        except subprocess.CalledProcessError:
            return False

    def update(self, see):
        """update infos"""
        failed = 0
        while failed < self._count:  # check more times if host in unreachable
            if self.ping():
                break
            failed += 1

        if not self.mac and not failed:
            self.set_mac(self._get_mac())
        if self.mac and failed < self._count:
            see(
                dev_id=self.dev_id,
                mac=self.mac,
            )
        else:
            _LOGGER.debug("ping KO on ip=%s failed=%d",
                          self.ip_address, failed)


def setup_scanner(hass, config, see):
    """initialize"""
    hosts = [Host(ip, hass, config) for ip in config[const.CONF_HOSTS]]
    interval = timedelta(seconds=len(hosts) * config[CONF_PING_COUNT] +
                         DEFAULT_SCAN_INTERVAL)
    _LOGGER.info("started ping tracker with interval=%s on hosts: %s",
                 interval, ",".join([host.ip_address for host in hosts]))

    def update(now):
        """update called every interval time"""
        for host in hosts:
            host.update(see)
        track_point_in_utc_time(hass, update, now + interval)
        return True

    return update(util.dt.utcnow())
