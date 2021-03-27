"""Support for the Rainforest Eagle-200 energy monitor."""
from datetime import timedelta
import logging

from eagle200_reader import EagleReader
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from uEagle import Eagle as LegacyReader
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_IP_ADDRESS,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

CONF_CLOUD_ID = "cloud_id"
CONF_INSTALL_CODE = "install_code"
POWER_KILO_WATT = "kW"

_LOGGER = logging.getLogger(__name__)

MIN_SCAN_INTERVAL = timedelta(seconds=30)

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


def hwtest(cloud_id, install_code, ip_address):
    """Try API call 'get_network_info' to see if target device is Legacy or Eagle-200."""
    reader = LeagleReader(cloud_id, install_code, ip_address)
    response = reader.get_network_info()

    # Branch to test if target is Legacy Model
    if (
        "NetworkInfo" in response
        and response["NetworkInfo"].get("ModelId", None) == "Z109-EAGLE"
    ):
        return reader

    # Branch to test if target is Eagle-200 Model
    if (
        "Response" in response
        and response["Response"].get("Command", None) == "get_network_info"
    ):
        return EagleReader(ip_address, cloud_id, install_code)

    # Catch-all if hardware ID tests fail
    raise ValueError("Couldn't determine device model.")


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the Eagle-200 sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    cloud_id = config[CONF_CLOUD_ID]
    install_code = config[CONF_INSTALL_CODE]

    try:
        eagle_reader = hwtest(cloud_id, install_code, ip_address)
    except (ConnectError, HTTPError, Timeout, ValueError) as error:
        _LOGGER.error("Failed to connect during setup: %s", error)
        return

    eagle_data = EagleData(eagle_reader)
    eagle_data.update()
    monitored_conditions = list(SENSORS)
    sensors = []
    for condition in monitored_conditions:
        sensors.append(
            EagleSensor(
                eagle_data, condition, SENSORS[condition][0], SENSORS[condition][1]
            )
        )

    add_entities(sensors)


class EagleSensor(SensorEntity):
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


class LeagleReader(LegacyReader, SensorEntity):
    """Wraps uEagle to make it behave like eagle_reader, offering update()."""

    def update(self):
        """Fetch and return the four sensor values in a dict."""
        out = {}

        resp = self.get_instantaneous_demand()["InstantaneousDemand"]
        out["instantanous_demand"] = resp["Demand"]

        resp = self.get_current_summation()["CurrentSummation"]
        out["summation_delivered"] = resp["SummationDelivered"]
        out["summation_received"] = resp["SummationReceived"]
        out["summation_total"] = out["summation_delivered"] - out["summation_received"]

        return out
