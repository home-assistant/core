"""Support for Meteoclimatic sensor."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteoclimatic sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [MeteoclimaticSensor(coordinator, description) for description in SENSOR_TYPES],
        False,
    )


class MeteoclimaticSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Meteoclimatic sensor."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(
        self, coordinator: DataUpdateCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize the Meteoclimatic sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        station = self.coordinator.data["station"]
        self._attr_name = f"{station.name} {description.name}"
        self._attr_unique_id = f"{station.code}_{description.key}"

    @property
    def device_info(self):
        """Return the device info."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.coordinator.name,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return (
            getattr(self.coordinator.data["weather"], self.entity_description.key)
            if self.coordinator.data
            else None
        )
