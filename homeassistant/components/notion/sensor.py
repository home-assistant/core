"""Support for Notion sensors."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NotionEntity
from .const import DOMAIN, LOGGER, SENSOR_TEMPERATURE

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Notion sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NotionSensor(
                coordinator,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                description,
            )
            for task_id, task in coordinator.data["tasks"].items()
            for description in SENSOR_DESCRIPTIONS
            if description.key == task["task_type"]
            and (sensor := coordinator.data["sensors"][task["sensor_id"]])
        ]
    )


class NotionSensor(NotionEntity, SensorEntity):
    """Define a Notion sensor."""

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
