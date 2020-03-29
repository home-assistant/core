"""Support for the Airly sensor service."""
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_NAME,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_API_HUMIDITY,
    ATTR_API_PM1,
    ATTR_API_PRESSURE,
    ATTR_API_TEMPERATURE,
    DOMAIN,
)

ATTRIBUTION = "Data provided by Airly"

ATTR_ICON = "icon"
ATTR_LABEL = "label"
ATTR_UNIT = "unit"

SENSOR_TYPES = {
    ATTR_API_PM1: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_API_PM1,
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    ATTR_API_HUMIDITY: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: None,
        ATTR_LABEL: ATTR_API_HUMIDITY.capitalize(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_API_PRESSURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_ICON: None,
        ATTR_LABEL: ATTR_API_PRESSURE.capitalize(),
        ATTR_UNIT: PRESSURE_HPA,
    },
    ATTR_API_TEMPERATURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: ATTR_API_TEMPERATURE.capitalize(),
        ATTR_UNIT: TEMP_CELSIUS,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Airly sensor entities based on a config entry."""
    name = config_entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []
    for sensor in SENSOR_TYPES:
        unique_id = f"{config_entry.unique_id}-{sensor.lower()}"
        sensors.append(AirlySensor(coordinator, name, sensor, unique_id))

    async_add_entities(sensors, False)


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res)
        return res

    return _decorator


class AirlySensor(Entity):
    """Define an Airly sensor."""

    def __init__(self, coordinator, name, kind, unique_id):
        """Initialize."""
        self.coordinator = coordinator
        self._name = name
        self._unique_id = unique_id
        self.kind = kind
        self._device_class = None
        self._state = None
        self._icon = None
        self._unit_of_measurement = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name."""
        return f"{self._name} {SENSOR_TYPES[self.kind][ATTR_LABEL]}"

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def state(self):
        """Return the state."""
        self._state = self.coordinator.data[self.kind]
        if self.kind in [ATTR_API_PM1, ATTR_API_PRESSURE]:
            self._state = round(self._state)
        if self.kind in [ATTR_API_TEMPERATURE, ATTR_API_HUMIDITY]:
            self._state = round(self._state, 1)
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
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
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.kind][ATTR_UNIT]

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self):
        """Update Airly entity."""
        await self.coordinator.async_request_refresh()
