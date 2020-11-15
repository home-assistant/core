"""Support for Hydrawise cloud switches."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import (
    ALLOWED_WATERING_TIME,
    CONF_WATERING_TIME,
    DATA_HYDRAWISE,
    DEFAULT_WATERING_TIME,
    SWITCHES,
    HydrawiseEntity,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SWITCHES): vol.All(
            cv.ensure_list, [vol.In(SWITCHES)]
        ),
        vol.Optional(CONF_WATERING_TIME, default=DEFAULT_WATERING_TIME): vol.All(
            vol.In(ALLOWED_WATERING_TIME)
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data

    default_watering_timer = config.get(CONF_WATERING_TIME)

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        # Create a switch for each zone
        for zone in hydrawise.relays:
            sensors.append(HydrawiseSwitch(default_watering_timer, zone, sensor_type))

    add_entities(sensors, True)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def __init__(self, default_watering_timer, *args):
        """Initialize a switch for Hydrawise device."""
        super().__init__(*args)
        self._default_watering_timer = default_watering_timer

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        relay_data = self.data["relay"] - 1
        if self._sensor_type == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(
                self._default_watering_timer, relay_data
            )
        elif self._sensor_type == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(0, relay_data)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        relay_data = self.data["relay"] - 1
        if self._sensor_type == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(0, relay_data)
        elif self._sensor_type == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(365, relay_data)

    def update(self):
        """Update device state."""
        relay_data = self.data["relay"] - 1
        mydata = self.hass.data[DATA_HYDRAWISE].data
        _LOGGER.debug("Updating Hydrawise switch: %s", self._name)
        if self._sensor_type == "manual_watering":
            self._state = mydata.relays[relay_data]["timestr"] == "Now"
        elif self._sensor_type == "auto_watering":
            self._state = (mydata.relays[relay_data]["timestr"] != "") and (
                mydata.relays[relay_data]["timestr"] != "Now"
            )
