"""
Support for RFXtrx binary sensors.

At the moment, only Lighting4 devices (cheap sensors based on PT2262)
have been tested.

This is experimental work!

"""

import logging
import voluptuous as vol
from datetime import timedelta
from homeassistant.components import rfxtrx
from homeassistant.util import slugify
from homeassistant.util import dt as dt_util
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import event as evt
from homeassistant.const import (CONF_SENSOR_CLASS)
from homeassistant.components.binary_sensor import (
    SENSOR_CLASSES, SENSOR_CLASSES_SCHEMA, BinarySensorDevice
)
from homeassistant.const import (STATE_ON, STATE_OFF)
from homeassistant.components.rfxtrx import (
    ATTR_AUTOMATIC_ADD, ATTR_NAME, ATTR_ENTITY_ID, ATTR_FIREEVENT, ATTR_OFF_DELAY,
    ATTR_SENSOR_CLASS, ATTR_PT2262_DATABITS, ATTR_CMD_ON, ATTR_CMD_OFF, CONF_DEVICES
)

DEPENDENCIES = ["rfxtrx"]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required("platform"): rfxtrx.DOMAIN,
    vol.Optional(CONF_DEVICES, default={}): vol.All(dict, rfxtrx.valid_binary_sensor),
    vol.Optional(ATTR_AUTOMATIC_ADD, default=False):  cv.boolean,
}, extra=vol.ALLOW_EXTRA)

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Binary Sensor platform to rfxtrx."""
    import RFXtrx as rfxtrxmod
    sensors = []

    for packet_id, entity in config['devices'].items():
        event = rfxtrx.get_rfx_object(packet_id)
        device_id = slugify(event.device.id_string.lower())

        if device_id in rfxtrx.RFX_DEVICES:
            continue

        if not entity[ATTR_PT2262_DATABITS] is None:
            _LOGGER.info("Masked deviceid: %s", (rfxtrx.get_masked_deviceid(device_id, 4)))
        
        _LOGGER.info("Add %s rfxtrx.binary_sensor (class %s)",
        entity[ATTR_NAME], entity[ATTR_SENSOR_CLASS])

        device = RfxtrxBinarySensor(event, entity[ATTR_NAME],
        entity[ATTR_SENSOR_CLASS], entity[ATTR_OFF_DELAY], 
        entity[ATTR_PT2262_DATABITS], entity[ATTR_CMD_ON], entity[ATTR_CMD_OFF])

        sensors.append(device)
        rfxtrx.RFX_DEVICES[device_id] = device

    add_devices_callback(sensors)

    def binary_sensor_update(event):
        """Callback for control updates from the RFXtrx gateway."""
        if not isinstance(event, rfxtrxmod.ControlEvent):
            return

        device_id = slugify(event.device.id_string.lower())

        if device_id in rfxtrx.RFX_DEVICES:
            sensor = rfxtrx.RFX_DEVICES[device_id]
        else:
            sensor = rfxtrx.get_pt2262_device(device_id)

        if sensor is None:
            return

        _LOGGER.info("Binary sensor update "
                     "(Device_id: %s Class: %s Sub: %s)",
                     slugify(event.device.id_string.lower()),
                     event.device.__class__.__name__,
                     event.device.subtype)

        prev_state = sensor.is_on

        if sensor.is_pt2262:
            cmd = rfxtrx.get_masked_cmd(device_id, sensor.data_bits)
            _LOGGER.info("applying cmd %s to device_id: %s)",
                     cmd, sensor.masked_id)
            sensor.apply_cmd(int(cmd, 16))
        else:
            sensor.update_state(True)

        if sensor.is_on == True:
            if sensor.off_delay is None:
               return
            elif sensor.off_delay == 0:
                sensor.update_state(False)
                return
            else:
                if sensor.delay_listener is None:
                    def off_delay_listener(now):
                      """switch device off after a delay."""
                      sensor.delay_listener = None
                      sensor.update_state(False)

                    sensor.delay_listener = evt.track_point_in_time(
                        hass, off_delay_listener, dt_util.utcnow() + timedelta(seconds = sensor.off_delay)
                    )

    # Subscribe to main rfxtrx events
    if binary_sensor_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(binary_sensor_update)


class RfxtrxBinarySensor(BinarySensorDevice):
    """A Rfxtrx binary sensor."""

    def __init__(self, event, name, sensor_class, off_delay = None, data_bits = None, cmd_on = None, cmd_off = None):
        """Initialize the sensor."""
        self.event = event
        self._name = name
        self._sensor_class = sensor_class
        self._off_delay = off_delay
        self._state = False
        self.delay_listener = None
        self._data_bits = data_bits
        self._cmd_on = cmd_on
        self._cmd_off = cmd_off
        
        if not data_bits is None:
            self._masked_id = rfxtrx.get_masked_deviceid(event.device.id_string.lower(), data_bits)
        else:
            self._masked_id = None
        
            
    def __str__(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def name(self):
        return self._name

    @property
    def is_pt2262(self):
        """Return true if the device is PT2262-based"""
        return not self._data_bits is None

    @property
    def masked_id(self):
        return self._masked_id
     
    @property
    def data_bits(self):
        return self._data_bits
    
    @property 
    def cmd_on(self):
        return self._cmd_on

    @property 
    def cmd_off(self):
        return self._cmd_off
        
    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def sensor_class(self):
        return self._sensor_class

    @property
    def off_delay(self):
        return self._off_delay

    @property
    def is_on(self):
        return self._state

    def apply_cmd(self, cmd):
        if (cmd == self.cmd_on):
            self.update_state(True)
        elif (cmd == self.cmd_off):
            self.update_state(False)

    def update_state(self, state):
        self._state = state
        self.update_ha_state()

