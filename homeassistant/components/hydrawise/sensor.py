"""Support for Hydrawise sprinkler sensors."""
import logging
import time

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DATA_HYDRAWISE, SENSORS, HydrawiseEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSORS): vol.All(
            cv.ensure_list, [vol.In(SENSORS)]
        )
    }
)

ONE_YEAR_SECONDS = 60 * 60 * 24 * 365


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        for zone in hydrawise.relays:
            sensors.append(HydrawiseSensor(zone, sensor_type))

    add_entities(sensors, True)


class HydrawiseSensor(HydrawiseEntity):
    """A sensor implementation for Hydrawise device."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        mydata = self.hass.data[DATA_HYDRAWISE].data
        _LOGGER.debug("Updating Hydrawise sensor: %s", self._name)
        relay_data = mydata.relays[self.data["relay"] - 1]
        if self._sensor_type == "watering_time":
            if relay_data["timestr"] == "Now":
                self._state = int(relay_data["run"] / 60)
            else:
                self._state = 0
        else:  # _sensor_type == 'next_cycle'
            _LOGGER.debug("New cycle time: %s", relay_data["time"])
            self._state = time.asctime(time.localtime(time.time() + relay_data["time"]))
