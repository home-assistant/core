"""Support for Ezviz sensors."""
import logging
from typing import Callable, List

from pyezviz.constants import SensorType

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, MANUFACTURER
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Ezviz sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    sensors = []
    sensor_type_name = "None"

    for idx, camera in enumerate(coordinator.data):
        for name in camera:
            if name in SensorType.__members__:
                sensor_type_name = getattr(SensorType, name).value
                sensors.append(EzvizSensor(coordinator, idx, name, sensor_type_name))

    async_add_entities(sensors)


class EzvizSensor(CoordinatorEntity, Entity):
    """Representation of a Ezviz sensor."""

    def __init__(self, coordinator, idx, name, sensor_type_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._idx = idx
        self._camera_name = self.coordinator.data[self._idx]["name"]
        self._name = name
        self._sensor_name = f"{self._camera_name}.{self._name}"
        self.sensor_type_name = sensor_type_name
        self._serial = self.coordinator.data[self._idx]["serial"]

    @property
    def name(self):
        """Return the name of the Ezviz sensor."""
        return self._sensor_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._idx][self._name]

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._serial}_{self._sensor_name}"

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": self.coordinator.data[self._idx]["name"],
            "model": self.coordinator.data[self._idx]["device_sub_category"],
            "manufacturer": MANUFACTURER,
        }

    @property
    def device_class(self):
        """Device class for the sensor."""
        return self.sensor_type_name
