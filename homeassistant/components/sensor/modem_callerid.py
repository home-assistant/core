"""
A sensor to monitor incoming calls using a USB modem that supports caller ID.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.modem_callerid/
"""
import logging
import threading
import datetime
import voluptuous as vol
from homeassistant.const import (STATE_IDLE,
                                 STATE_UNAVAILABLE,
                                 EVENT_HOMEASSISTANT_STOP,
                                 CONF_NAME,
                                 CONF_DEVICE,
                                 CONF_CODE)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyserial==3.1.1']

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'Modem CallerID'
ICON = 'mdi:phone-clasic'
DEFAULT_DEVICE = '/dev/ttyACM0'
DEFAULT_INITSTRING = 'AT#CID=1'

STATE_RING = 'ring'
STATE_CALLERID = 'callerid'

RING_TIMEOUT = 10
RING_WAIT = None

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_CODE, default=DEFAULT_INITSTRING): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup modem caller id sensor platform."""
    name = config.get(CONF_NAME)
    dev = config.get(CONF_DEVICE)
    init_string = config.get(CONF_CODE) + '\r\n'
    add_devices([ModemCalleridSensor(hass, name, dev, init_string)])


class ModemCalleridSensor(Entity):
    """Implementation of USB modem callerid."""

    def __init__(self, hass, name, dev, init_string):
        """Initialize the sensor."""
        self._state = STATE_IDLE
        self._attributes = {"cid_time": 0, "cid_number": '', "cid_name": ''}
        self._name = name
        self.dev = dev
        self.init_string = init_string
        self.ser = None

        threading.Thread(target=self._modem_sm, daemon=True).start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self._stop_modem)

    def set_state(self, state):
        """Set the state."""
        self._state = state

    def set_attributes(self, attributes):
        """Set the state attributes."""
        self._attributes = attributes

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return icon."""
        return ICON

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

    def _stop_modem(self, event):
        """HA is shutting down, close modem port."""
        if self.ser:
            self.ser.close()
            self.ser = None
        return

    def _modem_sm(self):
        """Handle modem state machine."""
        import serial
        cid_number = ''
        cid_time = 0
        ring_timer = RING_WAIT
        _LOGGER.info('Open port %s', self.dev)
        try:
            self.ser = serial.Serial(port=self.dev)
        except serial.SerialException:
            _LOGGER.error('Unable to open port %s', self.dev)
            self.set_state(STATE_UNAVAILABLE)
            self.update_ha_state()
            return

        _LOGGER.info('Write init string %s', self.init_string.encode())
        try:
            self.ser.write(self.init_string.encode())
        except serial.SerialException:
            _LOGGER.error('Unable to write to port %s', self.dev)
            self.set_state(STATE_UNAVAILABLE)
            self.update_ha_state()
            return

        while self.ser:
            self.ser.timeout = ring_timer
            try:
                resp = self.ser.readline()
            except serial.SerialException:
                _LOGGER.error('Unable to read from port %s', self.dev)
                self.set_state(STATE_UNAVAILABLE)
                self.update_ha_state()
                break

            if self.state != STATE_IDLE and len(resp) == 0:
                ring_timer = RING_WAIT
                self.set_state(STATE_IDLE)
                self.update_ha_state()
                continue

            resp = resp.decode()
            resp = resp.strip('\r\n')
            _LOGGER.info('mdm: %s', resp)
            if resp == '':
                continue

            if resp in ['RING']:
                if self.state == STATE_IDLE:
                    att = {"cid_time": datetime.datetime.now(),
                           "cid_number": '',
                           "cid_name": '',
                           "cid_formatted": ''}
                    self.set_attributes(att)

                self.set_state(STATE_RING)
                ring_timer = RING_TIMEOUT
                self.update_ha_state()
                continue

            if resp in ['ERROR']:
                self.set_state(STATE_UNAVAILABLE)
                self.update_ha_state()
                break

            if len(resp) <= 4:
                continue

            ring_timer = RING_TIMEOUT
            cid_field, cid_data = resp.split('=')
            cid_field = cid_field.strip()
            cid_data = cid_data.strip()
            if cid_field in ['DATE']:
                cid_time = datetime.datetime.now()
                cid_number = ''
                continue

            if cid_field in ['TIME']:
                continue

            if cid_field in ['NMBR']:
                cid_number = cid_data
                continue

            if cid_field in ['NAME']:
                att = {"cid_time": cid_time,
                       "cid_number": cid_number,
                       "cid_name": cid_data}
                self.set_attributes(att)
                self.set_state(STATE_CALLERID)
                self.update_ha_state()
                _LOGGER.info('CID: %s %s %s',
                             cid_time.strftime("%I:%M %p"),
                             cid_data,
                             cid_number)
                self.ser.write(self.init_string.encode())
                continue

            continue

        _LOGGER.info('Exiting USB modem state machine')
        return
