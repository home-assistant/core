"""IHC binary sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ihc/
"""
from xml.etree.ElementTree import Element

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA)
from homeassistant.components.ihc import (
    validate_name, IHC_DATA, IHC_CONTROLLER, IHC_INFO)
from homeassistant.components.ihc.const import CONF_INVERTING
from homeassistant.components.ihc.ihcdevice import IHCDevice
from homeassistant.const import (
    CONF_NAME, CONF_TYPE, CONF_ID, CONF_BINARY_SENSORS)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BINARY_SENSORS, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_ID): cv.positive_int,
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
                vol.Optional(CONF_INVERTING, default=False): cv.boolean,
            }, validate_name)
        ])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the IHC binary sensor platform."""
    ihc_controller = hass.data[IHC_DATA][IHC_CONTROLLER]
    info = hass.data[IHC_DATA][IHC_INFO]
    devices = []
    if discovery_info:
        for name, device in discovery_info.items():
            ihc_id = device['ihc_id']
            product_cfg = device['product_cfg']
            product = device['product']
            sensor = IHCBinarySensor(ihc_controller, name, ihc_id, info,
                                     product_cfg.get(CONF_TYPE),
                                     product_cfg[CONF_INVERTING],
                                     product)
            devices.append(sensor)
    else:
        binary_sensors = config[CONF_BINARY_SENSORS]
        for sensor_cfg in binary_sensors:
            ihc_id = sensor_cfg[CONF_ID]
            name = sensor_cfg[CONF_NAME]
            sensor_type = sensor_cfg.get(CONF_TYPE)
            inverting = sensor_cfg[CONF_INVERTING]
            sensor = IHCBinarySensor(ihc_controller, name, ihc_id, info,
                                     sensor_type, inverting)
            devices.append(sensor)

    add_devices(devices)


class IHCBinarySensor(IHCDevice, BinarySensorDevice):
    """IHC Binary Sensor.

    The associated IHC resource can be any in or output from a IHC product
    or function block, but it must be a boolean ON/OFF resources.
    """

    def __init__(self, ihc_controller, name, ihc_id: int, info: bool,
                 sensor_type: str, inverting: bool,
                 product: Element = None) -> None:
        """Initialize the IHC binary sensor."""
        super().__init__(ihc_controller, name, ihc_id, info, product)
        self._state = None
        self._sensor_type = sensor_type
        self.inverting = inverting

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._state

    def on_ihc_change(self, ihc_id, value):
        """IHC resource has changed."""
        if self.inverting:
            self._state = not value
        else:
            self._state = value
        self.schedule_update_ha_state()
