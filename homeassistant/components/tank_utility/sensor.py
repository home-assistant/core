"""Support for the Tank Utility propane monitor."""

from __future__ import annotations

import datetime
import logging

import requests
from tank_utility import auth, device as tank_monitor
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD, PERCENTAGE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(hours=1)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, vol.Length(min=1)),
    }
)

SENSOR_TYPE = "tank"
SENSOR_ROUNDING_PRECISION = 1
SENSOR_ATTRS = [
    "name",
    "address",
    "capacity",
    "fuelType",
    "orientation",
    "status",
    "time",
    "time_iso",
]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tank Utility sensor."""

    email = config[CONF_EMAIL]
    password = config[CONF_PASSWORD]
    devices = config[CONF_DEVICES]

    try:
        token = auth.get_token(email, password)
    except requests.exceptions.HTTPError as http_error:
        if http_error.response.status_code == requests.codes.unauthorized:
            _LOGGER.error("Invalid credentials")
            return

    all_sensors = []
    for device in devices:
        sensor = TankUtilitySensor(email, password, token, device)
        all_sensors.append(sensor)
    add_entities(all_sensors, True)


class TankUtilitySensor(SensorEntity):
    """Representation of a Tank Utility sensor."""

    def __init__(self, email, password, token, device):
        """Initialize the sensor."""
        self._email = email
        self._password = password
        self._token = token
        self._device = device
        self._state = None
        self._name = f"Tank Utility {self.device}"
        self._unit_of_measurement = PERCENTAGE
        self._attributes = {}

    @property
    def device(self):
        """Return the device identifier."""
        return self._device

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the device."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the attributes of the device."""
        return self._attributes

    def get_data(self):
        """Get data from the device.

        Flatten dictionary to map device to map of device data.

        """

        data = {}
        try:
            data = tank_monitor.get_device_data(self._token, self.device)
        except requests.exceptions.HTTPError as http_error:
            if http_error.response.status_code in (
                requests.codes.unauthorized,
                requests.codes.bad_request,
            ):
                _LOGGER.info("Getting new token")
                self._token = auth.get_token(self._email, self._password, force=True)
                data = tank_monitor.get_device_data(self._token, self.device)
            else:
                raise
        data.update(data.pop("device", {}))
        data.update(data.pop("lastReading", {}))
        return data

    def update(self) -> None:
        """Set the device state and attributes."""
        data = self.get_data()
        self._state = round(data[SENSOR_TYPE], SENSOR_ROUNDING_PRECISION)
        self._attributes = {k: v for k, v in data.items() if k in SENSOR_ATTRS}
