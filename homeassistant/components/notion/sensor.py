"""Support for Notion sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import NotionEntity
from .const import DATA_COORDINATOR, DOMAIN, LOGGER, SENSOR_TEMPERATURE

SENSOR_TYPES = {SENSOR_TEMPERATURE: ("Temperature", "temperature", TEMP_CELSIUS)}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Notion sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

    sensor_list = []
    for task_id, task in coordinator.data["tasks"].items():
        if task["task_type"] not in SENSOR_TYPES:
            continue

        name, device_class, unit = SENSOR_TYPES[task["task_type"]]
        sensor = coordinator.data["sensors"][task["sensor_id"]]

        sensor_list.append(
            NotionSensor(
                coordinator,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                name,
                device_class,
                unit,
            )
        )

    async_add_entities(sensor_list)


class NotionSensor(NotionEntity, SensorEntity):
    """Define a Notion sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        task_id: str,
        sensor_id: str,
        bridge_id: str,
        system_id: str,
        name: str,
        device_class: str,
        unit: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator, task_id, sensor_id, bridge_id, system_id, name, device_class
        )

        self._unit = unit

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        task = self.coordinator.data["tasks"][self.task_id]

        if task["task_type"] == SENSOR_TEMPERATURE:
            self._state = round(float(task["status"]["value"]), 1)
        else:
            LOGGER.error(
                "Unknown task type: %s: %s",
                self.coordinator.data["sensors"][self._sensor_id],
                task["task_type"],
            )
