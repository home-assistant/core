"""
Support for Netio devices

Configuraiton:
To use the Netio plugs you will need to add something like the following to
your config/configuration.yaml

switch:
    platform: netio
    host: SOME_IP
    name: living
    port: 1234
    username: admin
    password: admin

    1: Lampe
    2: Frigo
    4: TV
"""

import logging
import socket
import time
from datetime import timedelta
from telnetlib import Telnet
from threading import Lock
from homeassistant.helpers import validate_config
from homeassistant.helpers.entity import ToggleEntity
# from homeassistant.util import Throttle
from homeassistant.const import (
    DEVICE_DEFAULT_NAME, CONF_HOST, CONF_PORT, CONF_USERNAME,
    CONF_PASSWORD)
# from homeassistant.components.switch import ATTR_CURRENT_POWER_MWH

_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Read config and connect to devices """

    if not validate_config(dict(config=config),
                           dict(config=[CONF_HOST, ]), _LOGGER):
        return None

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT, "1234")
    username = config.get(CONF_USERNAME, "admin")
    password = config.get(CONF_PASSWORD, "admin")

    client = NetioDevice(host, port, username, password)
    # TODO Create a group with all switches from this NETIO

    devices = []
    for i in range(1, 5):
        if config.get(i):
            devices.append(
                NetioSwitch(client, i, config.get(i, DEVICE_DEFAULT_NAME)))

    add_devices(devices)
    return True


class NetioSwitch(ToggleEntity):

    """ Represents a four outlets Netio device """

    def __init__(self, netioClient, position, name):
        """ Let's initialize """
        self.netio = netioClient
        self.position = position
        self._name = name
        self._state = None
        self.update()

    @property
    def name(self):
        """ Name of the switch """
        return self._name

    @property
    def is_on(self):
        """ True if switch is on """
        return self._state

    @property
    def should_poll(self):
        """ No polling needed """
        return True

    def update(self):
        """ Update switch's state """
        self.netio.update()
        self._state = self.netio.states[self.position - 1]

    def turn_on(self, **kwargs):
        """ Turns the switch on """
        val = list('uuuu')
        val[self.position - 1] = '1'
        self._state = self.netio.get('port list %s' % ''.join(val))

    def turn_off(self, **kwargs):
        """ Turns the switch off """
        val = list('uuuu')
        val[self.position - 1] = '0'
        self._state = self.netio.get('port list %s' % ''.join(val))


class NetioDevice(object):
    MAX_RETRIES = 2

    """ Simple class to handle Telnet communication with the Netio's """

    def __init__(self, host, port, username, password):
        """ Let's initialize """
        self.host, self.port = host, port
        self.username, self.password = username, password
        self._states = []
        self.retries = self.MAX_RETRIES
        self.telnet = None
        self.lock = Lock()
        self.connect()

    def connect(self):
        """ Simple connect """
        try:
            self.telnet = Telnet(self.host, self.port)
            time.sleep(1)
            self.get()
            self.get('login admin admin')
        except socket.gaierror:
            _LOGGER.error("Cannot connect to %s (%d)" %
                          (self.host, self.retries))

    @property
    def states(self):
        """ Get the states """
        return self._states

    def update(self):
        """ Update all the switch values """

        self._states = [bool(int(x)) for x in self.get('port list') or '0000']

    # def keep_alive(self):
    #     self.get('version')

    def get(self, command=None):
        """
        Interface function to send and receive decoded bytes
        Retries the connect [self.retries] times

        """

        try:
            assert self.telnet
            with self.lock:
                if command:
                    if not command.endswith('\r\n'):
                        command += '\r\n'
                    _LOGGER.debug('%s: sending %r' % (self.host, command))
                    self.telnet.write(command.encode())

                res = self.telnet.read_until('\r\n'.encode()).decode()
                _LOGGER.debug('%s: received %r' % (self.host, res))
                if res.split()[0] not in ('100', '250'):
                    _LOGGER.warn('command error: %r' % res)
                return res.split()[1]

        except Exception:
            _LOGGER.error("Cannot get answer from %s (%d)" %
                          (self.host, self.retries))
            if self.retries > 0:
                self.retries -= 1
                self.connect()
                return self.get(command)
            else:
                self.retries = self.MAX_RETRIES
                return None

    def stop(self):
        """ Close the telnet connection """
        self.telnet.close()
