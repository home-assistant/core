"""Support for Meteoclimatic sensor."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.typing import HomeAssistantType
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

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_STATION_CODE = "station_code"
ATTR_STATION_NAME = "station_name"


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteoclimatic sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [MeteoclimaticSensor(sensor_type, coordinator) for sensor_type in SENSOR_TYPES],
        False,
    )


class MeteoclimaticSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Meteoclimatic sensor."""

    def __init__(self, sensor_type: str, coordinator: DataUpdateCoordinator):
        """Initialize the Meteoclimatic sensor."""
        super().__init__(coordinator)
        self._type = sensor_type
        station = self.coordinator.data["station"]
        self._name = f"{station.name} {SENSOR_TYPES[self._type][SENSOR_TYPE_NAME]}"
        self._unique_id = f"{station.code}_{self._type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_UNIT]

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_ICON]

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_CLASS]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {ATTR_ATTRIBUTION: ATTRIBUTION, ATTR_SENSOR_ID: self._type}
        if self.coordinator.data:
            attributes[ATTR_LAST_UPDATE] = self.coordinator.data["reception_time"]
            attributes[ATTR_STATION_CODE] = self.coordinator.data["station"].code
            attributes[ATTR_STATION_NAME] = self.coordinator.data["station"].name
        return attributes
