"""Platform for iammeter sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IammeterData
from .const import (
    DOMAIN,
    DEVICE_3080,
    DEVICE_3080T,
    SENSOR_TYPES_3080,
    SENSOR_TYPES_3080T,
    IammeterSensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Iammeter entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    print("ok")
    print(coordinator.data.model)
    if coordinator.data.model == DEVICE_3080:
        async_add_entities(
            IammeterSensor(coordinator, description)
            for description in SENSOR_TYPES_3080
        )
    if coordinator.data.model == DEVICE_3080T:
        async_add_entities(
            IammeterSensor(coordinator, description)
            for description in SENSOR_TYPES_3080T
        )


class IammeterSensor(update_coordinator.CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: IammeterSensorEntityDescription

    def __init__(
        self,
        coordinator: IammeterData,
        description: IammeterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer="IamMeter",
            name=coordinator.name,
        )
        print(coordinator.data.measurement)

    @property
    def native_value(self):
        """Return the native sensor value."""
        raw_attr = self.coordinator.data.measurement.get(self.entity_description.key, None)
        if self.entity_description.value:
            return self.entity_description.value(raw_attr)
        return raw_attr
