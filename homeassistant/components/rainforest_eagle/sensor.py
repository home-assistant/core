"""Support for the Rainforest Eagle-200 energy monitor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from eagle200_reader import EagleReader
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from uEagle import Eagle as LegacyReader
import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle, dt

CONF_CLOUD_ID = "cloud_id"
CONF_INSTALL_CODE = "install_code"
POWER_KILO_WATT = "kW"

_LOGGER = logging.getLogger(__name__)

MIN_SCAN_INTERVAL = timedelta(seconds=30)


@dataclass
class SensorType:
    """Rainforest sensor type."""

    name: str
    unit_of_measurement: str
    device_class: str | None = None
    state_class: str | None = None
    last_reset: datetime | None = None


SENSORS = {
    "instantanous_demand": SensorType(
        name="Eagle-200 Meter Power Demand",
        unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    "summation_delivered": SensorType(
        name="Eagle-200 Total Meter Energy Delivered",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt.utc_from_timestamp(0),
    ),
    "summation_received": SensorType(
        name="Eagle-200 Total Meter Energy Received",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt.utc_from_timestamp(0),
    ),
    "summation_total": SensorType(
        name="Eagle-200 Net Meter Energy (Delivered minus Received)",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
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

    add_entities(EagleSensor(eagle_data, condition) for condition in SENSORS)


class EagleSensor(SensorEntity):
    """Implementation of the Rainforest Eagle-200 sensor."""

    def __init__(self, eagle_data, sensor_type):
        """Initialize the sensor."""
        self.eagle_data = eagle_data
        self._type = sensor_type
        sensor_info = SENSORS[sensor_type]
        self._attr_name = sensor_info.name
        self._attr_unit_of_measurement = sensor_info.unit_of_measurement
        self._attr_device_class = sensor_info.device_class
        self._attr_state_class = sensor_info.state_class
        self._attr_last_reset = sensor_info.last_reset

    def update(self):
        """Get the energy information from the Rainforest Eagle."""
        self.eagle_data.update()
        self._attr_state = self.eagle_data.get_state(self._type)


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
