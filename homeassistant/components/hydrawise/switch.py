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
    DEVICE_MAP,
    DEVICE_MAP_INDEX,
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
        if self._sensor_type == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(
                self._default_watering_timer, (self.data["relay"] - 1)
            )
        elif self._sensor_type == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(
                0, (self.data["relay"] - 1)
            )

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._sensor_type == "manual_watering":
            self.hass.data[DATA_HYDRAWISE].data.run_zone(0, (self.data["relay"] - 1))
        elif self._sensor_type == "auto_watering":
            self.hass.data[DATA_HYDRAWISE].data.suspend_zone(
                365, (self.data["relay"] - 1)
            )

    def update(self):
        """Update device state."""
        mydata = self.hass.data[DATA_HYDRAWISE].data
        _LOGGER.debug("Updating Hydrawise switch: %s", self._name)
        if self._sensor_type == "manual_watering":
            if not mydata.running:
                self._state = False
            else:
                self._state = int(mydata.running[0]["relay"]) == self.data["relay"]
        elif self._sensor_type == "auto_watering":
            for relay in mydata.relays:
                if relay["relay"] == self.data["relay"]:
                    if relay.get("suspended") is not None:
                        self._state = False
                    else:
                        self._state = True
                    break

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return DEVICE_MAP[self._sensor_type][DEVICE_MAP_INDEX.index("ICON_INDEX")]
