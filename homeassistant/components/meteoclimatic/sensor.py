"""Support for Meteoclimatic sensor."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SENSOR_TYPE_CLASS,
    SENSOR_TYPE_ICON,
    SENSOR_TYPE_NAME,
    SENSOR_TYPE_UNIT,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteoclimatic sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [MeteoclimaticSensor(sensor_type, coordinator) for sensor_type in SENSOR_TYPES],
        False,
    )


class MeteoclimaticSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Meteoclimatic sensor."""

    def __init__(self, sensor_type: str, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the Meteoclimatic sensor."""
        super().__init__(coordinator)
        self._type = sensor_type
        station = self.coordinator.data["station"]
        self._attr_device_class = SENSOR_TYPES[sensor_type].get(SENSOR_TYPE_CLASS)
        self._attr_icon = SENSOR_TYPES[sensor_type].get(SENSOR_TYPE_ICON)
        self._attr_name = (
            f"{station.name} {SENSOR_TYPES[sensor_type][SENSOR_TYPE_NAME]}"
        )
        self._attr_unique_id = f"{station.code}_{sensor_type}"
        self._attr_unit_of_measurement = SENSOR_TYPES[sensor_type].get(SENSOR_TYPE_UNIT)

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.platform.config_entry.unique_id)},
            "name": self.coordinator.name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "entry_type": "service",
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        return (
            getattr(self.coordinator.data["weather"], self._type)
            if self.coordinator.data
            else None
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
