"""Sensor to monitor incoming/outgoing phone calls on a Fritz!Box router."""
from datetime import datetime, timedelta
import logging
import queue
from threading import Event as ThreadingEvent, Thread
from time import sleep

from fritzconnection.core.fritzmonitor import FritzMonitor
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_PREFIXES,
    CONF_PHONEBOOK,
    CONF_PREFIXES,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PHONEBOOK,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    FRITZ_STATE_CALL,
    FRITZ_STATE_CONNECT,
    FRITZ_STATE_DISCONNECT,
    FRITZ_STATE_RING,
    FRITZBOX_PHONEBOOK,
    ICON_PHONE,
    MANUFACTURER,
    SERIAL_NUMBER,
    STATE_DIALING,
    STATE_IDLE,
    STATE_RINGING,
    STATE_TALKING,
    UNKNOWN_NAME,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=3)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
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
    fritzbox_phonebook = hass.data[DOMAIN][config_entry.entry_id][FRITZBOX_PHONEBOOK]

    phonebook_name = config_entry.title
    phonebook_id = config_entry.data[CONF_PHONEBOOK]
    prefixes = config_entry.options.get(CONF_PREFIXES)
    serial_number = config_entry.data[SERIAL_NUMBER]
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]

    name = f"{fritzbox_phonebook.fph.modelname} Call Monitor {phonebook_name}"
    unique_id = f"{serial_number}-{phonebook_id}"

    sensor = FritzBoxCallSensor(
        name=name,
        unique_id=unique_id,
        fritzbox_phonebook=fritzbox_phonebook,
        prefixes=prefixes,
        host=host,
        port=port,
    )

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, sensor.async_will_remove_from_hass()
    )

    async_add_entities([sensor])


class FritzBoxCallSensor(SensorEntity):
    """Implementation of a Fritz!Box call monitor."""

    def __init__(self, name, unique_id, fritzbox_phonebook, prefixes, host, port):
        """Initialize the sensor."""
        self._state = STATE_IDLE
        self._attributes = {}
        self._name = name.title()
        self._unique_id = unique_id
        self._fritzbox_phonebook = fritzbox_phonebook
        self._prefixes = prefixes
        self._host = host
        self._port = port
        self._monitor = None

    async def async_added_to_hass(self):
        """Connect to FRITZ!Box to monitor its call state."""
        _LOGGER.debug("Starting monitor for: %s", self.entity_id)
        self._monitor = FritzBoxCallMonitor(
            host=self._host,
            port=self._port,
            sensor=self,
        )
        self._monitor.connect()

    async def async_will_remove_from_hass(self):
        """Disconnect from FRITZ!Box by stopping monitor."""
        if (
            self._monitor
            and self._monitor.stopped
            and not self._monitor.stopped.is_set()
            and self._monitor.connection
            and self._monitor.connection.is_alive
        ):
            self._monitor.stopped.set()
            self._monitor.connection.stop()
            _LOGGER.debug("Stopped monitor for: %s", self.entity_id)

    def set_state(self, state):
        """Set the state."""
        self._state = state

    def set_attributes(self, attributes):
        """Set the state attributes."""
        self._attributes = attributes

    @property
    def name(self):
        """Return name of this sensor."""
        return self._name

    @property
    def should_poll(self):
        """Only poll to update phonebook, if defined."""
        return self._fritzbox_phonebook is not None

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_PHONE

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._prefixes:
            self._attributes[ATTR_PREFIXES] = self._prefixes
        return self._attributes

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self._fritzbox_phonebook.fph.modelname,
            "identifiers": {(DOMAIN, self._unique_id)},
            "manufacturer": MANUFACTURER,
            "model": self._fritzbox_phonebook.fph.modelname,
            "sw_version": self._fritzbox_phonebook.fph.fc.system_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._unique_id

    def number_to_name(self, number):
        """Return a name for a given phone number."""
        if self._fritzbox_phonebook is None:
            return UNKNOWN_NAME
        return self._fritzbox_phonebook.get_name(number)

    def update(self):
        """Update the phonebook if it is defined."""
        if self._fritzbox_phonebook is not None:
            self._fritzbox_phonebook.update_phonebook()


class FritzBoxCallMonitor:
    """Event listener to monitor calls on the Fritz!Box."""

    def __init__(self, host, port, sensor):
        """Initialize Fritz!Box monitor instance."""
        self.host = host
        self.port = port
        self.connection = None
        self.stopped = ThreadingEvent()
        self._sensor = sensor

    def connect(self):
        """Connect to the Fritz!Box."""
        _LOGGER.debug("Setting up socket connection")
        try:
            self.connection = FritzMonitor(address=self.host, port=self.port)
            kwargs = {"event_queue": self.connection.start()}
            Thread(target=self._process_events, kwargs=kwargs).start()
        except OSError as err:
            self.connection = None
            _LOGGER.error(
                "Cannot connect to %s on port %s: %s", self.host, self.port, err
            )

    def _process_events(self, event_queue):
        """Listen to incoming or outgoing calls."""
        _LOGGER.debug("Connection established, waiting for events")
        while not self.stopped.is_set():
            try:
                event = event_queue.get(timeout=10)
            except queue.Empty:
                if not self.connection.is_alive and not self.stopped.is_set():
                    _LOGGER.error("Connection has abruptly ended")
                _LOGGER.debug("Empty event queue")
                continue
            else:
                _LOGGER.debug("Received event: %s", event)
                self._parse(event)
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
