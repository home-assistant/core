"""Support for the Rainforest Eagle-200 energy monitor."""
from datetime import timedelta
import logging

from requests.exceptions import (
    ConnectionError as ConnectError, HTTPError, Timeout)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_IP_ADDRESS, CONF_SCAN_INTERVAL, ENERGY_KILO_WATT_HOUR)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

CONF_CLOUD_ID = 'cloud_id'
CONF_INSTALL_CODE = 'install_code'
POWER_KILO_WATT = 'kW'

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

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
    vol.Required(CONF_INSTALL_CODE): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Create the Eagle-200 sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    cloud_id = config[CONF_CLOUD_ID]
    install_code = config[CONF_INSTALL_CODE]
    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

    eagle_data = EagleData(ip_address, cloud_id, install_code, interval)
    eagle_data.update()

    monitored_conditions = list(SENSORS)
    sensors = []
    for condition in monitored_conditions:
        sensors.append(EagleSensor(
            eagle_data, condition, SENSORS[condition][0],
            SENSORS[condition][1]))

    add_devices(sensors)


class EagleSensor(Entity):
    """Implementation of the Rainforest Eagle-200 sensor."""

    def __init__(
            self, eagle_data, sensor_type, name, unit):
        """Initialize the sensor."""
        self.eagle_data = eagle_data
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
        """Get the energy information from the Rainforest Eagle."""
        self.eagle_data.update()
        data = self.eagle_data.data
        self._state = self.get_state(data)

    def get_state(self, data):
        """Get the sensor value from the dictionary."""
        if data is None:
            return None

        state = data.get(self._type)
        return state


class EagleData:
    """Get the latest data from the Eagle-200 device."""

    def __init__(self, ip_address, cloud_id, install_code, interval):
        """Initialize the data object."""
        self._ip_address = ip_address
        self._cloud_id = cloud_id
        self._install_code = install_code
        self.interval = interval

        self.data = {}

        # Apply throttling to update method using configured interval.
        self.update = Throttle(interval)(self._update)

    def _update(self):
        """Get the latest data from the Eagle-200 device."""
        from eagle200_reader import EagleReader

        try:
            eagle_reader = EagleReader(
                self._ip_address, self._cloud_id, self._install_code)

            for sensor_type in SENSORS:
                self.data.update({sensor_type: getattr(
                    eagle_reader, sensor_type)()})
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            _LOGGER.error("Unable to connect to the Eagle-200: %s", error)
            self.data = None
