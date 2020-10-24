"""Support for AquaLogic sensors."""

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import DOMAIN, UPDATE_TOPIC

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = [PERCENTAGE, PERCENTAGE]
SALT_UNITS = ["g/L", "PPM"]
WATT_UNITS = [POWER_WATT, POWER_WATT]
NO_UNITS = [None, None]

# sensor_type [ description, unit, icon ]
# sensor_type corresponds to property names in aqualogic.core.AquaLogic
SENSOR_TYPES = {
    "air_temp": ["Air Temperature", TEMP_UNITS, "mdi:thermometer"],
    "pool_temp": ["Pool Temperature", TEMP_UNITS, "mdi:oil-temperature"],
    "spa_temp": ["Spa Temperature", TEMP_UNITS, "mdi:oil-temperature"],
    "pool_chlorinator": ["Pool Chlorinator", PERCENT_UNITS, "mdi:gauge"],
    "spa_chlorinator": ["Spa Chlorinator", PERCENT_UNITS, "mdi:gauge"],
    "salt_level": ["Salt Level", SALT_UNITS, "mdi:gauge"],
    "pump_speed": ["Pump Speed", PERCENT_UNITS, "mdi:speedometer"],
    "pump_power": ["Pump Power", WATT_UNITS, "mdi:gauge"],
    "status": ["Status", NO_UNITS, "mdi:alert"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    sensors = []

    processor = hass.data[DOMAIN]
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(AquaLogicSensor(processor, sensor_type))

    async_add_entities(sensors)


class AquaLogicSensor(Entity):
    """Sensor implementation for the AquaLogic component."""

    def __init__(self, processor, sensor_type):
        """Initialize sensor."""
        self._processor = processor
        self._type = sensor_type
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"AquaLogic {SENSOR_TYPES[self._type][0]}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        panel = self._processor.panel
        if panel is None:
            return None
        if panel.is_metric:
            return SENSOR_TYPES[self._type][1][0]
        return SENSOR_TYPES[self._type][1][1]

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self._type][2]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                UPDATE_TOPIC, self.async_update_callback
            )
        )

    @callback
    def async_update_callback(self):
        """Update callback."""
        panel = self._processor.panel
        if panel is not None:
            self._state = getattr(panel, self._type)
            self.async_write_ha_state()
