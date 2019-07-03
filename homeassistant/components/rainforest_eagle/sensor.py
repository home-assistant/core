"""Support for the Rainforest Eagle-200 energy monitor."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_IP_ADDRESS, CONF_MONITORED_CONDITIONS, ENERGY_KILO_WATT_HOUR)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

CONF_CLOUD_ID = 'cloud_id'
CONF_INSTALL_CODE = 'install_code'
POWER_KILO_WATT = 'kW'

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    "instantanous_demand": (
        "Eagle-200 Meter Power Demand", POWER_KILO_WATT),
    "summation_delivered": (
        "Eagle-200 Total Meter Energy Delivered",
        ENERGY_KILO_WATT_HOUR),
    "summation_received": (
        "Eagle-200 Total Meter Energy Received",
        ENERGY_KILO_WATT_HOUR),
    "summation_total": (
        "Eagle-200 Net Meter Energy (Delivered minus Received)",
        ENERGY_KILO_WATT_HOUR)
        }

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_CLOUD_ID): cv.string,
    vol.Required(CONF_INSTALL_CODE): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(list(SENSORS))])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Create the Eagle-200 sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    cloud_id = config[CONF_CLOUD_ID]
    install_code = config[CONF_INSTALL_CODE]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    for condition in monitored_conditions:
        add_devices([Eagle(ip_address, cloud_id, install_code, condition,
                           SENSORS[condition][0], SENSORS[condition][1])])


class Eagle(Entity):
    """Implementation of the Rainforest Eagle-200 sensor."""

    def __init__(
            self, ip_address, cloud_id, install_code, sensor_type, name, unit):
        """Initialize the sensor."""
        self._ip_address = ip_address
        self._cloud_id = cloud_id
        self._install_code = install_code
        self._type = sensor_type
        self._name = name
        self._unit_of_measurement = unit
        self._state = None

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
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Get the energy demand from the Rainforest Eagle."""
        from eagle200_reader import EagleReader

        self._state = getattr(EagleReader(
            self._ip_address, self._cloud_id,
            self._install_code), self._type)()
