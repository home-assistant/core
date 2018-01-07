"""IHC sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ihc/
"""
from xml.etree.ElementTree import Element
import voluptuous as vol

from homeassistant.components.ihc import validate_name, IHC_DATA
from homeassistant.components.ihc.const import CONF_AUTOSETUP
from homeassistant.components.ihc.ihcdevice import IHCDevice
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ID, CONF_NAME, CONF_TYPE, CONF_UNIT_OF_MEASUREMENT, CONF_SENSORS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_AUTOSETUP, default='False'): cv.boolean,
    vol.Optional(CONF_SENSORS, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_ID): cv.positive_int,
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_TYPE, default='Temperature'): cv.string,
                vol.Optional(CONF_UNIT_OF_MEASUREMENT, default='°C'): cv.string
            }, validate_name)
        ])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ihc sensor platform."""
    ihc = hass.data[IHC_DATA]
    devices = []
    if config.get(CONF_AUTOSETUP):
        def setup_product(ihc_id, name, product, product_cfg):
            """Product setup callback."""
            sensor = IHCSensor(ihc, name, ihc_id,
                               product_cfg[CONF_TYPE],
                               product_cfg[CONF_UNIT_OF_MEASUREMENT],
                               product)
            devices.append(sensor)
        ihc.product_auto_setup('sensor', setup_product)

    sensors = config.get(CONF_SENSORS)
    for sensor_cfg in sensors:
        ihc_id = sensor_cfg[CONF_ID]
        name = sensor_cfg[CONF_NAME]
        sensor_type = sensor_cfg[CONF_TYPE]
        unit = sensor_cfg[CONF_UNIT_OF_MEASUREMENT]
        sensor = IHCSensor(ihc, name, ihc_id, sensor_type, unit)
        devices.append(sensor)

    add_devices(devices)


class IHCSensor(IHCDevice, Entity):
    """Implementation of the IHC sensor."""

    def __init__(self, ihc, name, ihc_id, sensortype, unit,
                 product: Element = None):
        """Initialize the IHC sensor."""
        super().__init__(ihc, name, ihc_id, product)
        self._state = None
        self._icon = None
        self._assumed = False
        self.type = sensortype
        self._unit_of_measurement = unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def set_unit(self, unit):
        """Set unit of measusement."""
        self._unit_of_measurement = unit

    def on_ihc_change(self, ihc_id, value):
        """Callback when ihc resource changes."""
        self._state = value
        self.schedule_update_ha_state()
