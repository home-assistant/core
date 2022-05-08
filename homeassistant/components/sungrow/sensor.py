"""Platform for Sungrow Solar sensors."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SungrowData
from .const import DOMAIN, SENSOR_TYPES, SungrowSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add solarlog entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SungrowSensor(coordinator, description) for description in SENSOR_TYPES
    )


class SungrowSensor(CoordinatorEntity[SungrowData], SensorEntity):
    """Representation of a Sensor."""

    entity_description: SungrowSensorEntityDescription

    def __init__(
        self,
        coordinator: SungrowData,
        description: SungrowSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer="Sungrow",
            name=coordinator.name,
            configuration_url=coordinator.config_url,
        )

    @property
    def native_value(self):
        """Return the native sensor value."""
        if not self.coordinator.data:
            return None
        raw_attr = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.value:
            return self.entity_description.value(raw_attr)
        return raw_attr
