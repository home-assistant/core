"""
Allows reading temperatures from ecoal/esterownik.pl controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ecoal_boiler/
"""

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.components.ecoal_boiler import DATA_ECOAL_BOILER
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

# Available temp sensor ids
SENSOR_IDS = (
    "outdoor_temp",
    "indoor_temp",
    "indoor2_temp",
    "domestic_hot_water_temp",
    "target_domestic_hot_water_temp",
    "feedwater_in_temp",
    "feedwater_out_temp",
    "target_feedwater_temp",
    "coal_feeder_temp",
    "exhaust_temp",
)

ENABLED_SCHEMA = {}
for tempsensor_id in SENSOR_IDS:
    ENABLED_SCHEMA[vol.Optional(tempsensor_id)] = cv.string
CONF_ENABLE = "enable"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_ENABLE): ENABLED_SCHEMA}
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ecoal sensors."""
    devices = []
    config_enable = config.get(CONF_ENABLE, {})
    ecoal_contr = hass.data[DATA_ECOAL_BOILER]
    for sensor_id in SENSOR_IDS:
        name = config_enable.get(sensor_id)
        if name:
            devices.append(EcoalTempSensor(ecoal_contr, name, sensor_id))
    add_devices(devices, True)


class EcoalTempSensor(Entity):
    """Representation of a temperature sensor using ecoal status data."""

    def __init__(self, ecoal_contr, name, status_attr):
        """Initialize the sensor."""
        self._ecoal_contr = ecoal_contr
        self._name = name
        self._status_attr = status_attr
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        # Old values read 0.5 back can still be used
        status = self._ecoal_contr.get_cached_status()
        self._state = getattr(status, self._status_attr)
