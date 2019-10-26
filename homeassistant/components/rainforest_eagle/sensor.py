"""Support for Rainforest Eagle energy monitors."""
import logging

from eagle200_reader import EagleReader
from uEagle import Eagle as LegacyReader

from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_IP_ADDRESS,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle


from .const import (
    CONF_CLOUD_ID,
    CONF_INSTALL_CODE,
    POWER_KILO_WATT,
    MIN_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# {'sensor_label' : ('Nice Name', units)}
SENSORS = {
    "instantanous_demand": ("Eagle-200 Meter Power Demand", POWER_KILO_WATT),
    "summation_delivered": (
        "Eagle-200 Total Meter Energy Delivered",
        ENERGY_KILO_WATT_HOUR,
    ),
    "summation_received": (
        "Eagle-200 Total Meter Energy Received",
        ENERGY_KILO_WATT_HOUR,
    ),
    "summation_total": (
        "Eagle-200 Net Meter Energy (Delivered minus Received)",
        ENERGY_KILO_WATT_HOUR,
    ),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_CLOUD_ID): cv.string,
        vol.Required(CONF_INSTALL_CODE): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery=None):
    """Create the Eagle sensor via yaml."""
    ip_address = config[CONF_IP_ADDRESS]
    cloud_id = config[CONF_CLOUD_ID]
    install_code = config[CONF_INSTALL_CODE]

    # Don't set up if already in the entries database
    for other_eagle in hass.config_entries.async_entries(DOMAIN):
        if ip_address == other_eagle.data[CONF_IP_ADDRESS]:
            return True

    try:
        eagle_reader = await hwtest(cloud_id, install_code, ip_address)
    except (ConnectError, HTTPError, Timeout, ValueError) as error:
        _LOGGER.error("Failed to connect during setup: %s", error)
        return

    # create cache class to hold readings
    eagle_data = EagleData(eagle_reader)

    # get first set of data (OPTIONAL?)
    eagle_data.update()

    # add each 'sensor', actually just different data from same device
    to_add = []
    for this_sensor in SENSORS:
        this_sensor_entity = EagleSensor(
            eagle_data, this_sensor, SENSORS[this_sensor][0], SENSORS[this_sensor][1]
        )
        to_add.append(this_sensor_entity)
    async_add_entities(to_add)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up an Eagle config entry."""
    ip_address = config_entry.data[CONF_IP_ADDRESS]
    cloud_id = config_entry.data[CONF_CLOUD_ID]
    install_code = config_entry.data[CONF_INSTALL_CODE]

    try:
        eagle_reader = await hwtest(cloud_id, install_code, ip_address)
    except (ConnectError, HTTPError, Timeout, ValueError) as error:
        _LOGGER.error("Failed to connect during setup: %s", error)
        return

    # create cache class to hold readings
    eagle_data = EagleData(eagle_reader)

    # get first set of data (OPTIONAL?)
    eagle_data.update()

    # add each 'sensor', actually just different data from same device
    to_add = []
    for this_sensor in SENSORS:
        this_sensor_entity = EagleSensor(
            eagle_data, this_sensor, SENSORS[this_sensor][0], SENSORS[this_sensor][1]
        )
        to_add.append(this_sensor_entity)
    async_add_entities(to_add)


async def hwtest(cloud_id, install_code, ip_address):
    """Try API call 'device_list' to see if target device is Legacy or Eagle-200."""
    reader = LeagleReader(cloud_id, install_code, ip_address)
    response = reader.post_cmd("device_list")
    if "Error" in response and "Unknown command" in response["Error"]["Text"]:
        return reader  # Probably a Legacy model
    elif "device_list" in response:
        return EagleReader(ip_address, cloud_id, install_code)  # Probably Eagle-200
    else:
        _LOGGER.error("Couldn't determine device model.")
        return False


class EagleSensor(Entity):
    """Implementation of the Rainforest Eagle-200 sensor."""

    def __init__(self, eagle_data, sensor_type, name, unit):
        """Initialize the sensor."""
        self.eagle_data = eagle_data
        self._type = sensor_type
        self._name = name
        self._unit_of_measurement = unit
        self._state = None

    @property
    def device_class(self):
        """Return the power device class for the instantanous_demand sensor."""
        if self._type == "instantanous_demand":
            return DEVICE_CLASS_POWER

        return None

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
        self._state = self.eagle_data.get_state(self._type)


class EagleData:
    """Get the latest data from the Eagle-200 device."""

    def __init__(self, eagle_reader):
        """Initialize the data object."""
        self._eagle_reader = eagle_reader
        self.data = {}

    @Throttle(MIN_SCAN_INTERVAL)
    def update(self):
        """Get the latest data from the Eagle-200 device."""
        try:
            self.data = self._eagle_reader.update()
            _LOGGER.debug("API data: %s", self.data)
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            _LOGGER.error("Unable to connect during update: %s", error)
            self.data = {}

    def get_state(self, sensor_type):
        """Get the sensor value from the dictionary."""
        state = self.data.get(sensor_type)
        _LOGGER.debug("Updating: %s - %s", sensor_type, state)
        return state


class LeagleReader(LegacyReader):
    """Wraps uEagle to make it behave like eagle_reader, offering update()."""

    def update(self):
        """Fetch and return the four sensor values in a dict."""
        d = {}

        resp = self.get_instantaneous_demand()["InstantaneousDemand"]
        d["instantanous_demand"] = resp["Demand"]

        resp = self.get_current_summation()["CurrentSummation"]
        d["summation_delivered"] = resp["SummationDelivered"]
        d["summation_received"] = resp["SummationReceived"]
        d["summation_total"] = d["summation_delivered"] - d["summation_received"]

        return d
