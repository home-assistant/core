"""Sensor to monitor incoming/outgoing phone calls on a Fritz!Box router."""
from datetime import datetime
import logging
from socket import (
    AF_INET,
    SO_KEEPALIVE,
    SOCK_STREAM,
    SOL_SOCKET,
    socket,
    timeout as SocketTimeout,
)
from threading import Event as ThreadingEvent, Thread
from time import sleep

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_PREFIXES,
    CONF_PHONEBOOK,
    CONF_PREFIXES,
    DEFAULT_HOST,
    DEFAULT_PHONEBOOK,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    FRITZ_BOX_PHONEBOOK_OBJECT,
    FRITZ_STATE_CALL,
    FRITZ_STATE_CONNECT,
    FRITZ_STATE_DISCONNECT,
    FRITZ_STATE_RING,
    ICON_PHONE,
    INTERVAL_RECONNECT,
    MANUFACTURER,
    SERIAL_NUMBER,
    STATE_DIALING,
    STATE_IDLE,
    STATE_RINGING,
    STATE_TALKING,
    UNKOWN_NAME,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PHONEBOOK, default=DEFAULT_PHONEBOOK): cv.positive_int,
        vol.Optional(CONF_PREFIXES): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the platform into a config entry."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the fritzbox_callmonitor sensor from config_entry."""
    phonebook = hass.data[DOMAIN][config_entry.entry_id][FRITZ_BOX_PHONEBOOK_OBJECT]

    phonebook_name = config_entry.title
    phonebook_id = config_entry.data[CONF_PHONEBOOK]
    prefixes = config_entry.options.get(CONF_PREFIXES)
    serial_number = config_entry.data[SERIAL_NUMBER]

    name = f"{phonebook.fph.modelname} Call Monitor {phonebook_name}"
    unique_id = f"{serial_number}-{phonebook_id}"

    sensor = FritzBoxCallSensor(
        name=name,
        unique_id=unique_id,
        phonebook=phonebook,
        prefixes=prefixes,
    )

    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]

    monitor = FritzBoxCallMonitor(
        host=host,
        port=port,
        sensor=sensor,
    )
    monitor.connect()

    @callback
    def _stop_monitoring(event):
        """Stop monitoring."""
        monitor.stopped.set()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_monitoring)

    async_add_entities([sensor])


class FritzBoxCallSensor(Entity):
    """Implementation of a Fritz!Box call monitor."""

    def __init__(self, name, unique_id, phonebook, prefixes):
        """Initialize the sensor."""
        self._state = STATE_IDLE
        self._attributes = {}
        self._name = name
        self._unique_id = unique_id
        self._phonebook = phonebook
        self._prefixes = prefixes

    def set_state(self, state):
        """Set the state."""
        self._state = state

    def set_attributes(self, attributes):
        """Set the state attributes."""
        self._attributes = attributes

    @property
    def should_poll(self):
        """Only poll to update phonebook, if defined."""
        return self._phonebook is not None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_PHONE

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._prefixes:
            self._attributes[ATTR_PREFIXES] = self._prefixes
        return self._attributes

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self._phonebook.fph.modelname,
            "identifiers": {(DOMAIN, self._unique_id)},
            "manufacturer": MANUFACTURER,
            "model": self._phonebook.fph.modelname,
            "sw_version": self._phonebook.fph.fc.system_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._unique_id

    def number_to_name(self, number):
        """Return a name for a given phone number."""
        if self._phonebook is None:
            return UNKOWN_NAME
        return self._phonebook.get_name(number)

    def update(self):
        """Update the phonebook if it is defined."""
        if self._phonebook is not None:
            self._phonebook.update_phonebook()


class FritzBoxCallMonitor:
    """Event listener to monitor calls on the Fritz!Box."""

    def __init__(self, host, port, sensor):
        """Initialize Fritz!Box monitor instance."""
        self.host = host
        self.port = port
        self.sock = None
        self._sensor = sensor
        self.stopped = ThreadingEvent()

    def connect(self):
        """Connect to the Fritz!Box."""
        _LOGGER.debug("Setting up socket...")
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
        try:
            self.sock.connect((self.host, self.port))
            Thread(target=self._listen).start()
        except OSError as err:
            self.sock = None
            _LOGGER.error(
                "Cannot connect to %s on port %s: %s", self.host, self.port, err
            )

    def _listen(self):
        """Listen to incoming or outgoing calls."""
        _LOGGER.debug("Connection established, waiting for response...")
        while not self.stopped.isSet():
            try:
                response = self.sock.recv(2048)
            except SocketTimeout:
                # if no response after 10 seconds, just recv again
                continue
            response = str(response, "utf-8")
            _LOGGER.debug("Received %s", response)

            if not response:
                # if the response is empty, the connection has been lost.
                # try to reconnect
                _LOGGER.warning("Connection lost, reconnecting...")
                self.sock = None
                while self.sock is None:
                    self.connect()
                    sleep(INTERVAL_RECONNECT)
            else:
                line = response.split("\n", 1)[0]
                self._parse(line)
                sleep(1)

    def _parse(self, line):
        """Parse the call information and set the sensor states."""
        line = line.split(";")
        df_in = "%d.%m.%y %H:%M:%S"
        df_out = "%Y-%m-%dT%H:%M:%S"
        isotime = datetime.strptime(line[0], df_in).strftime(df_out)
        if line[1] == FRITZ_STATE_RING:
            self._sensor.set_state(STATE_RINGING)
            att = {
                "type": "incoming",
                "from": line[3],
                "to": line[4],
                "device": line[5],
                "initiated": isotime,
                "from_name": self._sensor.number_to_name(line[3]),
            }
            self._sensor.set_attributes(att)
        elif line[1] == FRITZ_STATE_CALL:
            self._sensor.set_state(STATE_DIALING)
            att = {
                "type": "outgoing",
                "from": line[4],
                "to": line[5],
                "device": line[6],
                "initiated": isotime,
                "to_name": self._sensor.number_to_name(line[5]),
            }
            self._sensor.set_attributes(att)
        elif line[1] == FRITZ_STATE_CONNECT:
            self._sensor.set_state(STATE_TALKING)
            att = {
                "with": line[4],
                "device": line[3],
                "accepted": isotime,
                "with_name": self._sensor.number_to_name(line[4]),
            }
            self._sensor.set_attributes(att)
        elif line[1] == FRITZ_STATE_DISCONNECT:
            self._sensor.set_state(STATE_IDLE)
            att = {"duration": line[3], "closed": isotime}
            self._sensor.set_attributes(att)
        self._sensor.schedule_update_ha_state()
