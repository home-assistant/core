"""Support for getting statistical data from a Pi-hole system."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import PiHoleDataUpdateCoordinator, PiHoleEntity
from .const import BINARY_SENSOR_DICT, BINARY_SENSOR_LIST, DOMAIN as PIHOLE_DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the pi-hole sensor."""
    coordinator = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    server_unique_id = coordinator.unique_id
    sensors = [
        PiHoleBinarySensor(coordinator, sensor_name, server_unique_id)
        for sensor_name in BINARY_SENSOR_LIST
    ]
    async_add_entities(sensors, True)


class PiHoleBinarySensor(PiHoleEntity, BinarySensorEntity):
    """Representation of a Pi-hole binary sensor."""

    def __init__(
        self,
        coordinator: PiHoleDataUpdateCoordinator,
        sensor_name: str,
        server_unique_id: str,
    ):
        """Initialize a Pi-hole sensor."""
        self._server_unique_id = server_unique_id
        variable_info = BINARY_SENSOR_DICT[sensor_name]
        self._condition = sensor_name
        condition_name = variable_info[0]
        self._on_value = variable_info[1]
        self._device_class = variable_info[2]
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
    def device_class(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._device_class

    @property
    def is_on(self) -> bool:
        """Return the state of the device."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get(self._condition) == self._on_value

        return None
