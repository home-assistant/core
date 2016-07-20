"""
Support for particulate matter sensors connected to a serial port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.particulate_matter/
"""
import logging
import threading
import time

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_SCAN_INTERVAL
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyserial']

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_DEVICE = "serial_device"
CONF_RECLEN = "record_length"
CONF_STARTBLOCK = "start_block"
CONF_BAUD = "baud"
CONF_DTR = "dtr"
CONF_STARTDELAY = "start_delay"
CONF_OFFSET_PM1 = "pm_1.0_offset"
CONF_OFFSET_PM2_5 = "pm_2.5_offset"
CONF_OFFSET_PM10 = "pm_10_offset"

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'particulate_matter',
    vol.Optional(CONF_NAME, default=""): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=300): cv.positive_int,
    vol.Required(CONF_SERIAL_DEVICE): cv.string,
    vol.Required(CONF_STARTBLOCK): cv.string,
    vol.Required(CONF_RECLEN): cv.positive_int,
    vol.Optional(CONF_OFFSET_PM1, default=0): cv.positive_int,
    vol.Optional(CONF_OFFSET_PM2_5, default=0): cv.positive_int,
    vol.Optional(CONF_OFFSET_PM10, default=0): cv.positive_int,
    vol.Optional(CONF_BAUD, default=9600): cv.positive_int,
    vol.Optional(CONF_STARTDELAY, default=10): cv.positive_int,
    vol.Optional(CONF_DTR, default=False): cv.boolean
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available PM sensors."""
    coll = PMDataCollector(config.get(CONF_SERIAL_DEVICE),
                           record_length=config.get(CONF_RECLEN),
                           start_sequence=config.get(CONF_STARTBLOCK),
                           baud_rate=config.get(CONF_BAUD),
                           dtr=config.get(CONF_DTR),
                           start_delay=config.get(CONF_STARTDELAY),
                           update_interval=config.get(CONF_SCAN_INTERVAL))

    dev = []

    if config.get(CONF_OFFSET_PM1) > 0:
        dev.append(ParticulateMatterSensor(coll, "PM1.0",
                                           config.get(CONF_OFFSET_PM1)))
    if config.get(CONF_OFFSET_PM2_5) > 0:
        dev.append(ParticulateMatterSensor(coll, "PM2.5",
                                           config.get(CONF_OFFSET_PM2_5)))
    if config.get(CONF_OFFSET_PM10) > 0:
        dev.append(ParticulateMatterSensor(coll, "PM10",
                                           config.get(CONF_OFFSET_PM10)))

    add_devices(dev)


class ParticulateMatterSensor(Entity):
    """Representation of an Particulate matter sensor."""

    # pylint: disable=too-many-arguments

    def __init__(self, pmDataCollector, name, offset):
        """Initialize a new PM sensor."""
        self._name = name
        self._state = 0
        pmDataCollector.add_listener(offset, self.update_data)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "µg/m³"

    def update_data(self, value):
        """Update the date to the given value.

        This is used from the PMDataCollector background thread
        """
        self._state = value
        if not self.should_poll:
            self.update_ha_state()
        _LOGGER.debug("State of %s updated to %s", self._name, self._state)


class PMDataCollector():
    """Controls the serial interface and reads data from teh sensor."""

# pylint: disable=too-many-arguments

    def __init__(self,
                 serialdevice,
                 start_sequence,
                 record_length,
                 dtr=False,
                 start_delay=10,
                 baud_rate=9600,
                 update_interval=300):
        """Initialize the data collector based on the given parameters."""
        import serial

        self.record_length = record_length
        self.start_sequence = bytes([0x32, 0x3d, 0x00, 0x1c])
        self.update_interval = update_interval
        self.listeners = []
        self.dtr = dtr
        self.start_delay = start_delay

        self.ser = serial.Serial(port=serialdevice,
                                 baudrate=baud_rate,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 bytesize=serial.EIGHTBITS)

        # Update date in using a background thread
        thread = threading.Thread(target=self.refresh, args=())
        thread.daemon = True
        thread.start()

    def refresh(self):
        """Background refreshing thread."""
        while True:
            self._update()
            time.sleep(self.update_interval)

# pylint: disable=too-many-branches
    def _update(self):
        """Read data from serial interface and send it to the listeners."""
        # Turn on circuit if DTR control is enabled
        if self.dtr is not None:
            if self.dtr:
                self.ser.setDTR(True)
            else:
                self.ser.setDTR(False)

            # Fan and circuit might need some seconds to warm up
            time.sleep(self.start_delay)

        finished = False
        buffer = bytearray()
        while not finished:
            if self.ser.inWaiting() > 0:
                buffer += self.ser.read(1)
                if len(buffer) == len(self.start_sequence):
                    if buffer == self.start_sequence:
                        _LOGGER.debug("Found start sequence %s",
                                      self.start_sequence)
                    else:
                        _LOGGER.debug("Start sequence not yet found")
                        # Remove first character
                        buffer = buffer[1:]

                if len(buffer) == self.record_length:
                    _LOGGER.debug("Finished reading data %s", buffer)
                    for [offset, callback] in self.listeners:
                        pmvalue = buffer[offset] * 256 + buffer[offset + 1]
                        callback(pmvalue)
                    finished = True
            else:
                time.sleep(.5)
                _LOGGER.debug("Serial waiting for data, buffer length=%s",
                              len(buffer))

        # Turn off the circuits again
        if self.dtr is not None:
            if self.dtr:
                self.ser.setDTR(False)
            else:
                self.ser.setDTR(True)

    def add_listener(self, offset, callback):
        """Add a listener that receives data stored at the given offset."""
        self.listeners.append([offset, callback])
