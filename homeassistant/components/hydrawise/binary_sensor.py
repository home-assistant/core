"""Support for Hydrawise sprinkler binary sensors."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import BINARY_SENSORS, DATA_HYDRAWISE, HydrawiseEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=BINARY_SENSORS): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSORS)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == "status":
            sensors.append(
                HydrawiseBinarySensor(hydrawise.current_controller, sensor_type)
            )
        else:
            # create a sensor for each zone
            for zone in hydrawise.relays:
                sensors.append(HydrawiseBinarySensor(zone, sensor_type))

    add_entities(sensors, True)


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating Hydrawise binary sensor: %s", self._name)
        mydata = self.hass.data[DATA_HYDRAWISE].data
        if self._sensor_type == "status":
            self._state = mydata.status == "All good!"
        elif self._sensor_type == "is_watering":
            relay_data = mydata.relays[self.data["relay"] - 1]
            self._state = relay_data["timestr"] == "Now"
