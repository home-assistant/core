"""
IHC binary sensor platform.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (STATE_UNKNOWN, CONF_NAME, CONF_TYPE,
                                 CONF_ID, CONF_BINARY_SENSORS)

from homeassistant.components.ihc.const import CONF_AUTOSETUP, CONF_INVERTING
from homeassistant.components.ihc import get_ihc_platform
from homeassistant.components.ihc.ihcdevice import IHCDevice

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_AUTOSETUP, default='False'): cv.boolean,
    vol.Optional(CONF_BINARY_SENSORS):
        [{
            vol.Required(CONF_ID): cv.positive_int,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_INVERTING): cv.boolean,
        }]
})


PRODUCTAUTOSETUP = [
    # Magnet contact
    {'xpath': './/product_dataline[@product_identifier="_0x2109"]',
     'node': 'dataline_input',
     'type': 'opening',
     'inverting': True},
    # Pir sensors
    {'xpath': './/product_dataline[@product_identifier="_0x210e"]',
     'node': 'dataline_input',
     'type': 'motion',
     'inverting': False},
    # Pir sensors twilight sensor
    {'xpath': './/product_dataline[@product_identifier="_0x0"]',
     'node': 'dataline_input',
     'type': 'motion',
     'inverting': False},
    # Pir sensors alarm
    {'xpath': './/product_dataline[@product_identifier="_0x210f"]',
     'node': 'dataline_input',
     'type': 'motion',
     'inverting': False},
    # Smoke detector
    {'xpath': './/product_dataline[@product_identifier="_0x210a"]',
     'node': 'dataline_input',
     'type': 'smoke',
     'inverting': False},
    # leak detector
    {'xpath': './/product_dataline[@product_identifier="_0x210c"]',
     'node': 'dataline_input',
     'type': 'moisture',
     'inverting': False},
    # light detector
    {'xpath': './/product_dataline[@product_identifier="_0x2110"]',
     'node': 'dataline_input',
     'type': 'light',
     'inverting': False},
]

_LOGGER = logging.getLogger(__name__)
_IHCBINARYSENSORS = {}


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the IHC binary setsor platform."""
    ihcplatform = get_ihc_platform(hass)
    devices = []
    if config.get(CONF_AUTOSETUP):
        auto_setup(ihcplatform, devices)

    binarysensors = config.get(CONF_BINARY_SENSORS)
    if binarysensors:
        _LOGGER.info("Adding IHC Binary Sensors")
        for binarysensor in binarysensors:
            ihcid = binarysensor[CONF_ID]
            name = (binarysensor[CONF_NAME]
                    if CONF_NAME in binarysensor
                    else "ihc_" + str(ihcid))
            sensortype = (binarysensor[CONF_TYPE]
                          if CONF_TYPE in binarysensor
                          else None)
            inverting = (binarysensor[CONF_INVERTING]
                         if CONF_INVERTING in binarysensor
                         else False)
            add_sensor(devices, ihcplatform.ihc, int(ihcid), name, sensortype,
                       True, inverting)

    add_devices(devices)
    # Start notification after devices has been added
    for device in devices:
        device.ihc.add_notify_event(device.get_ihcid(),
                                    device.on_ihc_change, True)


def auto_setup(ihcplatform, devices):
    """auto setup ihc binary sensors from ihc project."""
    _LOGGER.info("Auto setup - IHC Binary sensors")

    def setup_product(ihcid, name, product, productcfg):
        add_sensor_from_node(devices, ihcplatform.ihc, ihcid, name,
                             product, productcfg['type'],
                             productcfg['inverting'])
    ihcplatform.autosetup(PRODUCTAUTOSETUP, setup_product)


class IHCBinarySensor(IHCDevice, BinarySensorDevice):
    """IHC Binary Sensor."""
    def __init__(self, ihccontroller, name, ihcid, sensortype: str,
                 inverting: bool, ihcname: str, ihcnote: str,
                 ihcposition: str):
        IHCDevice.__init__(self, ihccontroller, name, ihcid, ihcname,
                           ihcnote, ihcposition)
        self._state = STATE_UNKNOWN
        self._sensor_type = sensortype
        self.inverting = inverting

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._state

    def update(self):
        pass

    def on_ihc_change(self, ihcid, value):
        """Callback when ihc resource changes."""
        if self.inverting:
            self._state = not value
        else:
            self._state = value
        self.schedule_update_ha_state()


def add_sensor_from_node(devices, ihccontroller, ihcid: int, name: str,
                         product, sensortype,
                         inverting: bool) -> IHCBinarySensor:
    """Add a sensor from the ihc project node."""
    ihcname = product.attrib['name']
    ihcnote = product.attrib['note']
    ihcposition = product.attrib['position']
    return add_sensor(devices, ihccontroller, ihcid, name, sensortype, False,
                      inverting, ihcname, ihcnote, ihcposition)


def add_sensor(devices, ihccontroller, ihcid: int, name: str,
               sensortype: str = None, overwrite: bool = False,
               inverting: bool = False, ihcname: str = "",
               ihcnote: str = "", ihcposition: str = "") -> IHCBinarySensor:
    """Add a new a sensor."""
    if ihcid in _IHCBINARYSENSORS:
        sensor = _IHCBINARYSENSORS[ihcid]
        if overwrite:
            sensor.set_name(name)
            _LOGGER.info("IHC sensor set name: " + name + " " + str(ihcid))
    else:
        sensor = IHCBinarySensor(ihccontroller, name, ihcid, sensortype,
                                 inverting, ihcname, ihcnote, ihcposition)
        _IHCBINARYSENSORS[ihcid] = sensor
        devices.append(sensor)
        _LOGGER.info("IHC sensor added: " + name + " " + str(ihcid))
    return sensor
