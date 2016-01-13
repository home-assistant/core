"""
Module to communicate with a O2 Box 1421, similar to https://hilfe.o2online.de/docs/DOC-1332
"""

import logging
from datetime import timedelta
from collections import namedtuple
import requests

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

wlandevice = namedtuple('WlanDevice', ['mac', 'name', 'ip', 'signal', 'link_rate'])

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """ Validates config and returns FritzBoxScanner. """
    if not validate_config(config,
                           {DOMAIN: []},
                           _LOGGER):
        return None

    scanner = O2BoxScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


class O2BoxScanner(object):
    """This class queries the O2Box"""
    def __init__(self, config):
        self.last_results = []
        self.password = ''
        self.success_init = True

        # Check for user specific configuration
        if CONF_HOST in config.keys():
            self.host = config[CONF_HOST]
        if CONF_PASSWORD in config.keys():
            self.password = config[CONF_PASSWORD]

        # Establish a connection to the FRITZ!Box
        self.o2_box = O2Box(host=self.host, routerpassword=self.password)

        if self.o2_box.try_login():
            self.success_init = True
            _LOGGER.info("Successfully connected to O2-Box")
            self._update_info()
        else:
            self.success_init = False
            _LOGGER.error("Failed to establish connection to O2Box "
                          "with IP: %s", self.host)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the FRITZ!Box. """
        if not self.success_init:
            return False

        _LOGGER.info("Scanning")
        self.last_results = self.o2_box.get_wireless_devices()
        return True

    def scan_devices(self):
        """ Scan for new devices and return a list of found device ids. """
        self._update_info()
        active_hosts = []
        for known_host in self.last_results:
            active_hosts.append(known_host.mac)
        return active_hosts

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if is not known. """
        self._update_info()
        for known_host in self.last_results:
            if known_host.mac == mac:
                return known_host.name

        return None


class O2Box(object):
    """This is the class which connects over HTTP to the O2Box
    and parses the HTML to extract information"""
    def __init__(self, host, routerpassword):
        self.baseurl = "http://{}".format(host)
        self.password = routerpassword

    @staticmethod
    def _pretty_mac(macugly):
        macs = macugly.replace('[', '').replace(']', '').replace('\'', '').split(',')
        return ':'.join(macs)

    def _extract_wireless_info(self, lines):
        """
        Extracts the info of all the wireless devices from the Javascript section of the HTML
        """
        clientlines = list(filter(lambda l: 'STA_infos[' in l and 'lan_client_t' not in l, lines))
        client_cnt = int(len(clientlines) / 4)

        def extract_client_infos():
            """Extract each client from the extracted STA infos from HTML"""
            for i in range(0, client_cnt):
                cclines = map(lambda cc: cc.split('.')[1],
                              (filter(lambda l: '[{0:d}]'.format(i) in l, clientlines)))
                cleaned = list(map(lambda cc: cc.replace(';', '').split('='), cclines))
                mac = signal = link_rate = None
                for key, val in cleaned:
                    if key == 'mac':
                        mac = self._pretty_mac(val)
                    if key == 'RSSI':
                        signal = int(val)
                    if key == 'rate':
                        link_rate = int(val)

                if mac is not None:
                    yield (mac, (signal, link_rate))

        return dict((m, rest) for m, rest in extract_client_infos())

    def _extract_dhcp_clients(self, lines):
        """
        Extracts all DHCP clients from the Javascript section of the HTML
        """
        clientlines = list(filter(lambda l: 'dhcpclients[' in l and '].' in l, lines))
        dhcp_cnt = int(len(clientlines) / 4)

        def extract_dhcp_clients():
            """extracts the name, mac and ip address"""
            for i in range(0, dhcp_cnt):
                cclines = map(lambda cc: cc.split('.')[1],
                              (filter(lambda l: '[%i]' % i in l, clientlines)))
                cleaned = map(lambda cc: cc.replace(';', '').replace(' ', '').replace('\'', '').split('='), cclines)
                macaddress = hostname = ipaddress = None
                for key, val in cleaned:
                    if key == 'name':
                        if val != '':
                            hostname = val
                    if key == 'mac':
                        macaddress = self._pretty_mac(val)
                    if key == 'ip':
                        ipparts = val.replace('[', '').replace(']', '').replace(' ', '').split(',')
                        ipaddress = '.'.join(ipparts)

                yield (macaddress, (hostname, ipaddress))

        return dict((m, rest) for m, rest in extract_dhcp_clients())

    def _login(self, session):
        """
        Login with current session
        Returns True when sucessful, False when unsuccessful
        """
        payload = {
            'controller': 'Overview',
            'action': 'Login',
            'id': '0',
            'idTextPassword': self.password
        }
        res = session.post(self.baseurl + '/cgi-bin/Hn_login.cgi', data=payload)
        lines = res.text.split('\n')
        for line in lines:
            if 'msgLoginPwd_err' in line:
                return False

        return True

    def _logout(self, session):
        """
        Always immediatly log out again, otherwise access to router would be blocked
        """
        session.get(self.baseurl + '/cgi-bin/Hn_logout.cgi')

    def try_login(self):
        """
        Tries to login and then logout
        Returns true if attemp was successful, false when unsuccessful
        """
        try:
            with requests.Session() as session:
                if self._login(session):
                    self._logout(session)
                    return True
                else:
                    return False
        except:
            _LOGGER.exception('error occured while logging in')
            return False

    def get_wireless_devices(self):
        """
        Returns a list of wireless devices connected to the router
        """
        with requests.Session() as session:
            if not self._login(session):
                _LOGGER.error("login failed")
                return None

            _LOGGER.debug("logged in")

            lanoverview = session.get(self.baseurl + '/lan_overview.htm')
            _LOGGER.debug("fetched lan overview")

            # log immediately out, access is blocked if not
            self._logout(session)
            _LOGGER.debug("logged out")

            def extract_wireless_information():
                """extracts the information from dhcp which returns the name and the ip address"""
                lines = lanoverview.text.split('\n')

                dhcpclients = self._extract_dhcp_clients(lines)

                for k, infos in self._extract_wireless_info(lines).items():
                    if k in dhcpclients:
                        name, ipaddress = dhcpclients[k]
                    else:
                        name = ipaddress = None

                    yield wlandevice(k, name, ipaddress, infos[0], infos[1])

            return list(extract_wireless_information())