"""Platform for FAA Delays sensor component."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_ICON, ATTR_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FAA_BINARY_SENSORS


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a FAA sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    binary_sensors = []
    for kind, attrs in FAA_BINARY_SENSORS.items():
        name = attrs[ATTR_NAME]
        icon = attrs[ATTR_ICON]

        binary_sensors.append(
            FAABinarySensor(coordinator, kind, name, icon, entry.entry_id)
        )

    async_add_entities(binary_sensors)


class FAABinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Define a binary sensor for FAA Delays."""

    def __init__(self, coordinator, sensor_type, name, icon, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.coordinator = coordinator
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._id = self.coordinator.data.iata
        self._attrs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._id} {self._name}"

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def is_on(self):
        """Return the status of the sensor."""
        if self._sensor_type == "GROUND_DELAY":
            return self.coordinator.data.ground_delay.status
        if self._sensor_type == "GROUND_STOP":
            return self.coordinator.data.ground_stop.status
        if self._sensor_type == "DEPART_DELAY":
            return self.coordinator.data.depart_delay.status
        if self._sensor_type == "ARRIVE_DELAY":
            return self.coordinator.data.arrive_delay.status
        if self._sensor_type == "CLOSURE":
            return self.coordinator.data.closure.status
        return None

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._id}_{self._sensor_type}"

    @property
    def extra_state_attributes(self):
        """Return attributes for sensor."""
        if self._sensor_type == "GROUND_DELAY":
            self._attrs["average"] = self.coordinator.data.ground_delay.average
            self._attrs["reason"] = self.coordinator.data.ground_delay.reason
        elif self._sensor_type == "GROUND_STOP":
            self._attrs["endtime"] = self.coordinator.data.ground_stop.endtime
            self._attrs["reason"] = self.coordinator.data.ground_stop.reason
        elif self._sensor_type == "DEPART_DELAY":
            self._attrs["minimum"] = self.coordinator.data.depart_delay.minimum
            self._attrs["maximum"] = self.coordinator.data.depart_delay.maximum
            self._attrs["trend"] = self.coordinator.data.depart_delay.trend
            self._attrs["reason"] = self.coordinator.data.depart_delay.reason
        elif self._sensor_type == "ARRIVE_DELAY":
            self._attrs["minimum"] = self.coordinator.data.arrive_delay.minimum
            self._attrs["maximum"] = self.coordinator.data.arrive_delay.maximum
            self._attrs["trend"] = self.coordinator.data.arrive_delay.trend
            self._attrs["reason"] = self.coordinator.data.arrive_delay.reason
        elif self._sensor_type == "CLOSURE":
            self._attrs["begin"] = self.coordinator.data.closure.begin
            self._attrs["end"] = self.coordinator.data.closure.end
            self._attrs["reason"] = self.coordinator.data.closure.reason
        return self._attrs
