"""Support for Notion sensors."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import NotionEntity
from .const import DATA_COORDINATOR, DOMAIN, LOGGER, SENSOR_TEMPERATURE

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    SENSOR_TEMPERATURE: SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Notion sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

    sensor_list = []
    for task_id, task in coordinator.data["tasks"].items():
        if task["task_type"] not in SENSOR_DESCRIPTIONS:
            continue

        sensor = coordinator.data["sensors"][task["sensor_id"]]
        sensor_list.append(
            NotionSensor(
                coordinator,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                SENSOR_DESCRIPTIONS[task["task_type"]],
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
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator, task_id, sensor_id, bridge_id, system_id, description
        )

        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        task = self.coordinator.data["tasks"][self._task_id]

        if task["task_type"] == SENSOR_TEMPERATURE:
            self._attr_native_value = round(float(task["status"]["value"]), 1)
        else:
            LOGGER.error(
                "Unknown task type: %s: %s",
                self.coordinator.data["sensors"][self._sensor_id],
                task["task_type"],
            )
