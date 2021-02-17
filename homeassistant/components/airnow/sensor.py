"""Support for the AirNow sensor service."""
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_API_AQI,
    ATTR_API_AQI_DESCRIPTION,
    ATTR_API_AQI_LEVEL,
    ATTR_API_O3,
    ATTR_API_PM25,
    DOMAIN,
    SENSOR_AQI_ATTR_DESCR,
    SENSOR_AQI_ATTR_LEVEL,
)

ATTRIBUTION = "Data provided by AirNow"

ATTR_ICON = "icon"
ATTR_LABEL = "label"
ATTR_UNIT = "unit"

PARALLEL_UPDATES = 1

SENSOR_TYPES = {
    ATTR_API_AQI: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_API_AQI,
        ATTR_UNIT: "aqi",
    },
    ATTR_API_PM25: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_API_PM25,
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    ATTR_API_O3: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_API_O3,
        ATTR_UNIT: CONCENTRATION_PARTS_PER_MILLION,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AirNow sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []
    for sensor in SENSOR_TYPES:
        sensors.append(AirNowSensor(coordinator, sensor))

    async_add_entities(sensors, False)


class AirNowSensor(CoordinatorEntity):
    """Define an AirNow sensor."""

    def __init__(self, coordinator, kind):
        """Initialize."""
        super().__init__(coordinator)
        self.kind = kind
        self._device_class = None
        self._state = None
        self._icon = None
        self._unit_of_measurement = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name."""
        return f"AirNow {SENSOR_TYPES[self.kind][ATTR_LABEL]}"

    @property
    def state(self):
        """Return the state."""
        self._state = self.coordinator.data[self.kind]
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.kind == ATTR_API_AQI:
            self._attrs[SENSOR_AQI_ATTR_DESCR] = self.coordinator.data[
                ATTR_API_AQI_DESCRIPTION
            ]
            self._attrs[SENSOR_AQI_ATTR_LEVEL] = self.coordinator.data[
                ATTR_API_AQI_LEVEL
            ]

        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        self._icon = SENSOR_TYPES[self.kind][ATTR_ICON]
        return self._icon

    @property
    def device_class(self):
        """Return the device_class."""
        return SENSOR_TYPES[self.kind][ATTR_DEVICE_CLASS]

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.coordinator.latitude}-{self.coordinator.longitude}-{self.kind.lower()}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.kind][ATTR_UNIT]
