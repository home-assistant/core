"""Support for AquaLogic sensors."""

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, UPDATE_TOPIC

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = [PERCENTAGE, PERCENTAGE]
SALT_UNITS = ["g/L", "PPM"]
WATT_UNITS = [POWER_WATT, POWER_WATT]
NO_UNITS = [None, None]

# sensor_type [ description, unit, icon, device_class ]
# sensor_type corresponds to property names in aqualogic.core.AquaLogic
SENSOR_TYPES = {
    "air_temp": ["Air Temperature", TEMP_UNITS, None, DEVICE_CLASS_TEMPERATURE],
    "pool_temp": [
        "Pool Temperature",
        TEMP_UNITS,
        "mdi:oil-temperature",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "spa_temp": [
        "Spa Temperature",
        TEMP_UNITS,
        "mdi:oil-temperature",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "pool_chlorinator": ["Pool Chlorinator", PERCENT_UNITS, "mdi:gauge", None],
    "spa_chlorinator": ["Spa Chlorinator", PERCENT_UNITS, "mdi:gauge", None],
    "salt_level": ["Salt Level", SALT_UNITS, "mdi:gauge", None],
    "pump_speed": ["Pump Speed", PERCENT_UNITS, "mdi:speedometer", None],
    "pump_power": ["Pump Power", WATT_UNITS, "mdi:gauge", None],
    "status": ["Status", NO_UNITS, "mdi:alert", None],
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


class AquaLogicSensor(SensorEntity):
    """Sensor implementation for the AquaLogic component."""

    _attr_should_poll = False

    def __init__(self, processor, sensor_type):
        """Initialize sensor."""
        self._processor = processor
        self._type = sensor_type
        self._attr_name = f"AquaLogic {SENSOR_TYPES[sensor_type][0]}"
        self._attr_icon = SENSOR_TYPES[sensor_type][2]

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
            if panel.is_metric:
                self._attr_unit_of_measurement = SENSOR_TYPES[self._type][1][0]
            else:
                self._attr_unit_of_measurement = SENSOR_TYPES[self._type][1][1]

            self._attr_state = getattr(panel, self._type)
            self.async_write_ha_state()
        else:
            self._attr_unit_of_measurement = None
