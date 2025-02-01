"""Support for the Torque OBD application."""

from __future__ import annotations

import re

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_EMAIL, CONF_NAME, DEGREE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

API_PATH = "/api/torque"

DEFAULT_NAME = "vehicle"
DOMAIN = "torque"

ENTITY_NAME_FORMAT = "{0} {1}"

SENSOR_EMAIL_FIELD = "eml"
SENSOR_NAME_KEY = r"userFullName(\w+)"
SENSOR_UNIT_KEY = r"userUnit(\w+)"
SENSOR_VALUE_KEY = r"k(\w+)"

NAME_KEY = re.compile(SENSOR_NAME_KEY)
UNIT_KEY = re.compile(SENSOR_UNIT_KEY)
VALUE_KEY = re.compile(SENSOR_VALUE_KEY)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def convert_pid(value):
    """Convert pid from hex string to integer."""
    return int(value, 16)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Torque platform."""
    vehicle: str | None = config.get(CONF_NAME)
    email: str | None = config.get(CONF_EMAIL)
    sensors: dict[int, TorqueSensor] = {}

    hass.http.register_view(
        TorqueReceiveDataView(email, vehicle, sensors, async_add_entities)
    )


class TorqueReceiveDataView(HomeAssistantView):
    """Handle data from Torque requests."""

    url = API_PATH
    name = "api:torque"

    def __init__(
        self,
        email: str | None,
        vehicle: str | None,
        sensors: dict[int, TorqueSensor],
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize a Torque view."""
        self.email = email
        self.vehicle = vehicle
        self.sensors = sensors
        self.async_add_entities = async_add_entities

    @callback
    def get(self, request: web.Request) -> str | None:
        """Handle Torque data request."""
        data = request.query

        if self.email is not None and self.email != data[SENSOR_EMAIL_FIELD]:
            return None

        names = {}
        units = {}
        for key in data:
            is_name = NAME_KEY.match(key)
            is_unit = UNIT_KEY.match(key)
            is_value = VALUE_KEY.match(key)

            if is_name:
                pid = convert_pid(is_name.group(1))
                names[pid] = data[key]
            elif is_unit:
                pid = convert_pid(is_unit.group(1))

                temp_unit = data[key]
                if "\\xC2\\xB0" in temp_unit:
                    temp_unit = temp_unit.replace("\\xC2\\xB0", DEGREE)

                units[pid] = temp_unit
            elif is_value:
                pid = convert_pid(is_value.group(1))
                if pid in self.sensors:
                    self.sensors[pid].async_on_update(data[key])

        new_sensor_entities: list[TorqueSensor] = []
        for pid, name in names.items():
            if pid not in self.sensors:
                torque_sensor_entity = TorqueSensor(
                    ENTITY_NAME_FORMAT.format(self.vehicle, name), units.get(pid)
                )
                new_sensor_entities.append(torque_sensor_entity)
                self.sensors[pid] = torque_sensor_entity

        if new_sensor_entities:
            self.async_add_entities(new_sensor_entities)

        return "OK!"


class TorqueSensor(SensorEntity):
    """Representation of a Torque sensor."""

    def __init__(self, name, unit):
        """Initialize the sensor."""
        self._name = name
        self._unit = unit
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the default icon of the sensor."""
        return "mdi:car"

    @callback
    def async_on_update(self, value):
        """Receive an update."""
        self._state = value
        self.async_write_ha_state()
