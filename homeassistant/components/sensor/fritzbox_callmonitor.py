"""
A sensor to monitor incoming and outgoing phone calls on a Fritz!Box router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fritzbox_callmonitor/
"""
import logging
import socket
import threading
import datetime
import time
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_NAME,
                                 CONF_PASSWORD, CONF_USERNAME,
                                 EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['fritzconnection==0.6.5']

_LOGGER = logging.getLogger(__name__)

CONF_PHONEBOOK = 'phonebook'
CONF_PREFIXES = 'prefixes'

DEFAULT_HOST = '169.254.1.1'  # IP valid for all Fritz!Box routers
DEFAULT_NAME = 'Phone'
DEFAULT_PORT = 1012

INTERVAL_RECONNECT = 60

VALUE_CALL = 'dialing'
VALUE_CONNECT = 'talking'
VALUE_DEFAULT = 'idle'
VALUE_DISCONNECT = 'idle'
VALUE_RING = 'ringing'

# Return cached results if phonebook was downloaded less then this time ago.
MIN_TIME_PHONEBOOK_UPDATE = datetime.timedelta(hours=6)
SCAN_INTERVAL = datetime.timedelta(hours=3)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_PASSWORD, default='admin'): cv.string,
    vol.Optional(CONF_USERNAME, default=''): cv.string,
    vol.Optional(CONF_PHONEBOOK, default=0): cv.positive_int,
    vol.Optional(CONF_PREFIXES, default=[]):
        vol.All(cv.ensure_list, [cv.string])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Fritz!Box call monitor sensor platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    phonebook_id = config.get('phonebook')
    prefixes = config.get('prefixes')

    try:
        phonebook = FritzBoxPhonebook(
            host=host, port=port, username=username, password=password,
            phonebook_id=phonebook_id, prefixes=prefixes)
    except:  # noqa: E722 pylint: disable=bare-except
        phonebook = None
        _LOGGER.warning("Phonebook with ID %s not found on Fritz!Box",
                        phonebook_id)

    sensor = FritzBoxCallSensor(name=name, phonebook=phonebook)

    add_entities([sensor])

    monitor = FritzBoxCallMonitor(host=host, port=port, sensor=sensor)
    monitor.connect()

    def _stop_listener(_event):
        monitor.stopped.set()

    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_STOP,
        _stop_listener
    )

    return monitor.sock is not None


class FritzBoxCallSensor(Entity):
    """Implementation of a Fritz!Box call monitor."""

    def __init__(self, name, phonebook):
        """Initialize the sensor."""
        self._state = VALUE_DEFAULT
        self._attributes = {}
        self._name = name
        self.phonebook = phonebook

    def set_state(self, state):
        """Set the state."""
        self._state = state

    def set_attributes(self, attributes):
        """Set the state attributes."""
        self._attributes = attributes

    @property
    def should_poll(self):
        """Only poll to update phonebook, if defined."""
        return self.phonebook is not None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def number_to_name(self, number):
        """Return a name for a given phone number."""
        if self.phonebook is None:
            return 'unknown'
        return self.phonebook.get_name(number)

    def update(self):
        """Update the phonebook if it is defined."""
        if self.phonebook is not None:
            self.phonebook.update_phonebook()


class FritzBoxCallMonitor:
    """Event listener to monitor calls on the Fritz!Box."""

    def __init__(self, host, port, sensor):
        """Initialize Fritz!Box monitor instance."""
        self.host = host
        self.port = port
        self.sock = None
        self._sensor = sensor
        self.stopped = threading.Event()

    def connect(self):
        """Connect to the Fritz!Box."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        try:
            self.sock.connect((self.host, self.port))
            threading.Thread(target=self._listen).start()
        except socket.error as err:
            self.sock = None
            _LOGGER.error("Cannot connect to %s on port %s: %s",
                          self.host, self.port, err)

    def _listen(self):
        """Listen to incoming or outgoing calls."""
        while not self.stopped.isSet():
            try:
                response = self.sock.recv(2048)
            except socket.timeout:
                # if no response after 10 seconds, just recv again
                continue
            response = str(response, "utf-8")

            if not response:
                # if the response is empty, the connection has been lost.
                # try to reconnect
                self.sock = None
                while self.sock is None:
                    self.connect()
                    time.sleep(INTERVAL_RECONNECT)
            else:
                line = response.split("\n", 1)[0]
                self._parse(line)
                time.sleep(1)

    def _parse(self, line):
        """Parse the call information and set the sensor states."""
        line = line.split(";")
        df_in = "%d.%m.%y %H:%M:%S"
        df_out = "%Y-%m-%dT%H:%M:%S"
        isotime = datetime.datetime.strptime(line[0], df_in).strftime(df_out)
        if line[1] == "RING":
            self._sensor.set_state(VALUE_RING)
            att = {"type": "incoming",
                   "from": line[3],
                   "to": line[4],
                   "device": line[5],
                   "initiated": isotime}
            att["from_name"] = self._sensor.number_to_name(att["from"])
            self._sensor.set_attributes(att)
        elif line[1] == "CALL":
            self._sensor.set_state(VALUE_CALL)
            att = {"type": "outgoing",
                   "from": line[4],
                   "to": line[5],
                   "device": line[6],
                   "initiated": isotime}
            att["to_name"] = self._sensor.number_to_name(att["to"])
            self._sensor.set_attributes(att)
        elif line[1] == "CONNECT":
            self._sensor.set_state(VALUE_CONNECT)
            att = {"with": line[4], "device": line[3], "accepted": isotime}
            att["with_name"] = self._sensor.number_to_name(att["with"])
            self._sensor.set_attributes(att)
        elif line[1] == "DISCONNECT":
            self._sensor.set_state(VALUE_DISCONNECT)
            att = {"duration": line[3], "closed": isotime}
            self._sensor.set_attributes(att)
        self._sensor.schedule_update_ha_state()


class FritzBoxPhonebook:
    """This connects to a FritzBox router and downloads its phone book."""

    def __init__(self, host, port, username, password,
                 phonebook_id=0, prefixes=None):
        """Initialize the class."""
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.phonebook_id = phonebook_id
        self.phonebook_dict = None
        self.number_dict = None
        self.prefixes = prefixes or []

        import fritzconnection as fc  # pylint: disable=import-error
        # Establish a connection to the FRITZ!Box.
        self.fph = fc.FritzPhonebook(
            address=self.host, user=self.username, password=self.password)

        if self.phonebook_id not in self.fph.list_phonebooks:
            raise ValueError("Phonebook with this ID not found.")

        self.update_phonebook()

    @Throttle(MIN_TIME_PHONEBOOK_UPDATE)
    def update_phonebook(self):
        """Update the phone book dictionary."""
        self.phonebook_dict = self.fph.get_all_names(self.phonebook_id)
        self.number_dict = {re.sub(r'[^\d\+]', '', nr): name
                            for name, nrs in self.phonebook_dict.items()
                            for nr in nrs}
        _LOGGER.info("Fritz!Box phone book successfully updated")

    def get_name(self, number):
        """Return a name for a given phone number."""
        number = re.sub(r'[^\d\+]', '', str(number))
        if self.number_dict is None:
            return 'unknown'
        try:
            return self.number_dict[number]
        except KeyError:
            pass
        if self.prefixes:
            for prefix in self.prefixes:
                try:
                    return self.number_dict[prefix + number]
                except KeyError:
                    pass
                try:
                    return self.number_dict[prefix + number.lstrip('0')]
                except KeyError:
                    pass
        return 'unknown'
