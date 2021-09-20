"""Platform for solarlog sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.entity import StateType

from . import SolarlogData
from .const import DOMAIN, SENSOR_TYPES, SolarLogSensorEntityDescription


async def async_setup_entry(hass, entry, async_add_entities):
    """Add solarlog entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolarlogSensor(coordinator, description) for description in SENSOR_TYPES
    )


class SolarlogSensor(update_coordinator.CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: SolarLogSensorEntityDescription

    def __init__(
        self,
        coordinator: SolarlogData,
        description: SolarLogSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.unique_id)},
            "name": coordinator.name,
            "manufacturer": "Solar-Log",
        }

    @property
    def native_value(self) -> StateType:
        """Return the native sensor value."""
        result = getattr(self.coordinator.data, self.entity_description.key)
        if self.entity_description.factor:
            state = round(result * self.entity_description.factor, 3)
        else:
            state = result
        return state
