"""Support for reading vehicle status from ConnectedCars.io."""
import logging
from typing import Any, Callable, Dict, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    ATTR_ATTRIBUTION,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    DOMAIN,
    ATTR_API_VEHICLE_VIN,
    ATTR_API_VEHICLE_MAKE,
    ATTR_API_VEHICLE_MODEL,
    ATTR_API_VEHICLE_NAME,
    ATTR_API_VEHICLE_LICENSEPLATE,
    ATTR_API_VEHICLE_POS_LATITUDE,
    ATTR_API_VEHICLE_POS_LONGITUDE,
)

from . import ConnectedCarsDataUpdateCoordinator

ATTRIBUTION = "Data provided by ConnectedCars.io"

ATTR_ICON = "icon"
ATTR_LABEL = "label"

SENSOR_TYPES = {
    "position": {ATTR_ICON: "mdi:car-side", ATTR_LABEL: "position",},
}

# TODO: Use Logger where smart to do so
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Conncted Cars entities based on a config entry."""
    name = config_entry.title

    coordinator: ConnectedCarsDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    # TODO: Add vin to unique id
    sensors = []
    for sensor in SENSOR_TYPES:
        unique_id = f"{config_entry.unique_id}-{sensor.lower()}"
        sensors.append(ConnectedCarsTracker(coordinator, name, sensor, unique_id))

    async_add_entities(sensors, False)


class ConnectedCarsTracker(TrackerEntity):
    """Define an Connected Cars sensor."""

    def __init__(self, coordinator, name, kind, unique_id):
        """Initialize."""
        self.coordinator = coordinator
        self._name = name
        self._unique_id = unique_id
        self.kind = kind
        self._device_class = None
        self._icon = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name."""
        return f"{self.coordinator.data[ATTR_API_VEHICLE_LICENSEPLATE]} {SENSOR_TYPES[self.kind][ATTR_LABEL]}"

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self.coordinator.data[ATTR_API_VEHICLE_POS_LATITUDE]

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self.coordinator.data[ATTR_API_VEHICLE_POS_LONGITUDE]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def icon(self):
        """Return the icon."""
        self._icon = SENSOR_TYPES[self.kind][ATTR_ICON]
        return self._icon

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Connected Car."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.coordinator.data[ATTR_API_VEHICLE_VIN])},
            ATTR_NAME: self.coordinator.data[ATTR_API_VEHICLE_NAME],
            ATTR_MANUFACTURER: self.coordinator.data[ATTR_API_VEHICLE_MAKE],
            ATTR_MODEL: self.coordinator.data[ATTR_API_VEHICLE_MODEL],
        }

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update Airly entity."""
        await self.coordinator.async_request_refresh()
