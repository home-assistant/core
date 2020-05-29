"""Support for getting statistical data from a Pi-hole system."""
import logging
from typing import Any

from homeassistant.helpers.entity import Entity

from . import PiHoleDataUpdateCoordinator, PiHoleEntity
from .const import DOMAIN as PIHOLE_DOMAIN, SENSOR_DICT, SENSOR_LIST

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the pi-hole sensor."""
    coordinator = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    server_unique_id = coordinator.unique_id
    sensors = [
        PiHoleSensor(coordinator, sensor_name, server_unique_id)
        for sensor_name in SENSOR_LIST
    ]
    async_add_entities(sensors, True)


class PiHoleSensor(PiHoleEntity, Entity):
    """Representation of a Pi-hole sensor."""

    def __init__(
        self,
        coordinator: PiHoleDataUpdateCoordinator,
        sensor_name: str,
        server_unique_id: str,
    ):
        """Initialize a Pi-hole sensor."""
        self._condition = sensor_name
        self._server_unique_id = server_unique_id
        variable_info = SENSOR_DICT[sensor_name]
        condition_name = variable_info[0]
        self._unit_of_measurement = variable_info[1]
        self._icon = variable_info[2]
        super().__init__(
            coordinator=coordinator,
            name=f"{coordinator.name} {condition_name}",
            device_id=server_unique_id,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}_{self._condition}"

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
        if self.coordinator.data is None:
            return None
        try:
            return round(self.coordinator.data.get(self._condition), 2)
        except TypeError:
            return self.coordinator.data.get(self._condition)
