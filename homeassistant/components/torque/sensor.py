"""Support for the Torque OBD application."""

from __future__ import annotations

import logging
import re

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.components.torque.torque_pids import PIDS_INFO
from homeassistant.const import (
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_EMAIL,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import slugify

API_PATH = "/api/torque"

DEFAULT_NAME = "vehicle"
DOMAIN = "torque"

SENSOR_EMAIL_FIELD = "eml"
SENSOR_VALUE_KEY = r"k(\w+)"

VALUE_KEY = re.compile(SENSOR_VALUE_KEY)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


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
    vehicle: str = config[CONF_NAME]
    email: str | None = config.get(CONF_EMAIL)
    sensors: dict[str, TorqueSensor] = {}

    _LOGGER.debug(
        "Setting up Torque platform with vehicle: %s, email: %s",
        vehicle,
        email,
    )
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
        vehicle: str,
        sensors: dict[str, TorqueSensor],
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
        data: dict[str, str] = request.query
        _LOGGER.debug("Received data: %s", data)

        if self.email is not None and self.email != data[SENSOR_EMAIL_FIELD]:
            _LOGGER.debug(
                "Wrong email address: %s != %s",
                self.email,
                data[SENSOR_EMAIL_FIELD],
            )
            return None

        vehicle_id = data["id"]
        pids = {}
        for key, value in data.items():
            if key_match := VALUE_KEY.match(key):
                _LOGGER.debug("Found PID key: %s (hexa)", key)
                pid = key_match.group(1)
                pids.update({pid: value})
            elif key in ("v", "eml", "time", "id", "session"):
                _LOGGER.debug("Ignoring info key: %s with value: %s", key, value)
            else:
                _LOGGER.warning("Unrecognized key: %s", key)
                continue

        new_sensor_entities: list[TorqueSensor] = []
        for pid, value in pids.items():
            if pid not in self.sensors:
                _LOGGER.debug("Creating new sensor for PID %s", pid)

                # Try to find PID info using string key first, then convert to int if not found
                pid_info = PIDS_INFO.get(pid, PIDS_INFO.get(convert_pid(pid), {}))

                if not pid_info:
                    _LOGGER.warning("No PID info found for PID %s", pid)

                torque_sensor_entity = TorqueSensor(
                    vehicle_name=self.vehicle,
                    vehicle_id=vehicle_id,
                    pid=pid,
                    name=pid_info.get(ATTR_NAME, pid),
                    unit=pid_info.get(ATTR_UNIT_OF_MEASUREMENT),
                    icon=pid_info.get(ATTR_ICON, "mdi:car"),
                    initial_state=value,
                )
                new_sensor_entities.append(torque_sensor_entity)
                self.sensors[pid] = torque_sensor_entity
            else:
                _LOGGER.debug("Updating existing sensor for PID %s", pid)
                self.sensors[pid].async_on_update(value)

        if new_sensor_entities:
            self.async_add_entities(new_sensor_entities)

        _LOGGER.debug("End of Torque data processing for %s", self.vehicle)
        return "OK!"


class TorqueSensor(SensorEntity):
    """Representation of a Torque sensor."""

    def __init__(
        self,
        vehicle_name: str,
        vehicle_id: str,
        pid: str,
        name: str | None,
        unit: str | None,
        icon: str | None,
        initial_state: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{slugify(vehicle_id)}_{pid}"
        self._attr_name = f"{vehicle_name} {name}" if name else vehicle_name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._state = initial_state
        self._pid = pid  # Store the PID for reference
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, slugify(vehicle_id))},
            name=vehicle_name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional attributes about the sensor."""
        if self._pid:
            return {"pid": self._pid}
        return None

    @callback
    def async_on_update(self, value):
        """Receive an update."""
        self._state = value
        self.async_write_ha_state()
