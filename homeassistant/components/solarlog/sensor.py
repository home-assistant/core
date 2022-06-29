"""Platform for solarlog sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolarlogData
from .const import DOMAIN, SENSOR_TYPES, SolarLogSensorEntityDescription


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add solarlog entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolarlogSensor(coordinator, description) for description in SENSOR_TYPES
    )


class SolarlogSensor(CoordinatorEntity[SolarlogData], SensorEntity):
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer="Solar-Log",
            name=coordinator.name,
            configuration_url=coordinator.host,
        )

    @property
    def native_value(self):
        """Return the native sensor value."""
        raw_attr = getattr(self.coordinator.data, self.entity_description.key)
        if self.entity_description.value:
            return self.entity_description.value(raw_attr)
        return raw_attr
