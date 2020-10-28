"""Monitor the Informix UltraSync Hub"""

import logging
from homeassistant.const import CONF_USERNAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from typing import Callable, List, Optional

from . import UltraSyncEntity
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import UltraSyncDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "area01_state": ["Area1State", "Area 1 State", None],
    "area02_state": ["Area2State", "Area 2 State", None],
    "area03_state": ["Area3State", "Area 3 State", None],
    "area04_state": ["Area4State", "Area 4 State", None],
}


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up UltraSync sensor based on a config entry."""
    coordinator: UltraSyncDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    sensors = []

    for sensor_config in SENSOR_TYPES.values():
        sensors.append(
            UltraSyncSensor(
                coordinator,
                entry.entry_id,
                entry.data[CONF_USERNAME],
                sensor_config[0],
                sensor_config[1],
                sensor_config[2],
            )
        )

    async_add_entities(sensors)


class UltraSyncSensor(UltraSyncEntity):
    """Representation of a UltraSync sensor."""

    def __init__(
        self,
        coordinator: UltraSyncDataUpdateCoordinator,
        entry_id: str,
        entry_name: str,
        sensor_type: str,
        sensor_name: str,
        unit_of_measurement: Optional[str] = None,
    ):
        """Initialize a new UltraSync sensor."""
        self._sensor_type = sensor_type
        self._unique_id = f"{entry_id}_{sensor_type}"
        self._unit_of_measurement = unit_of_measurement

        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            name=f"{entry_name} {sensor_name}",
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._sensor_type)
        if value is None:
            _LOGGER.warning("Unable to locate value for %s", self._sensor_type)
            return None

        return value
