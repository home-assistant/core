"""Support for getting statistical data from a Pi-hole system."""
from __future__ import annotations

from typing import Any

from hole import Hole

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleEntity
from .const import (
    ATTR_BLOCKED_DOMAINS,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DOMAIN as PIHOLE_DOMAIN,
    SENSOR_DICT,
    SENSOR_LIST,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Pi-hole sensor."""
    name = entry.data[CONF_NAME]
    hole_data = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    sensors = [
        PiHoleSensor(
            hole_data[DATA_KEY_API],
            hole_data[DATA_KEY_COORDINATOR],
            name,
            sensor_name,
            entry.entry_id,
        )
        for sensor_name in SENSOR_LIST
    ]
    async_add_entities(sensors, True)


class PiHoleSensor(PiHoleEntity, SensorEntity):
    """Representation of a Pi-hole sensor."""

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator,
        name: str,
        sensor_name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize a Pi-hole sensor."""
        super().__init__(api, coordinator, name, server_unique_id)

        self._condition = sensor_name

        variable_info = SENSOR_DICT[sensor_name]
        self._condition_name = variable_info[0]
        self._unit_of_measurement = variable_info[1]
        self._icon = variable_info[2]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name} {self._condition_name}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._condition_name}"

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self) -> Any:
        """Return the state of the device."""
        try:
            return round(self.api.data[self._condition], 2)
        except TypeError:
            return self.api.data[self._condition]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the Pi-hole."""
        return {ATTR_BLOCKED_DOMAINS: self.api.data["domains_being_blocked"]}
