"""Support for Gogogate2 temperature."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "gogogate2"

NOTIFICATION_ID = "gogogate2_temperature"
NOTIFICATION_TITLE = "Gogogate2 Temperature"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Gogogate2 component."""
    from pygogogate2 import Gogogate2API as pygogogate2

    temp_unit = hass.config.units.temperature_unit

    ip_address = config.get(CONF_IP_ADDRESS)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)
    username = config.get(CONF_USERNAME)

    mygogogate2 = pygogogate2(username, password, ip_address)

    try:
        devices = mygogogate2.get_devices()
        if devices is False:
            raise ValueError("Username or Password is incorrect or no devices found")

        add_entities(
            MyGogogate2Thermostat(mygogogate2, door, temp_unit) for door in devices
        )

    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            "".format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )


class MyGogogate2Sensor(Entity):
    """Representation of a Gogogate2 temperature sensor."""

    def __init__(self, mygogogate2, device, temp_unit):
        """Initialize with API object, device id."""
        self.mygogogate2 = mygogogate2
        self.device_id = device["door"]
        self._name = device["name"]
        self._temperature = device["temperature"]
        self._temp_unit = temp_unit

    @property
    def name(self):
        """Return the name of the temperature sensor"""
        return self._name if self._name else DEFAULT_NAME

    @property
    def state(self):
        """Return the state of the entity."""
        return self._temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._temp_unit

    def update(self):
        """Cache value from pygogogate2"""
        try:
            # mygogogate2 always returns the temperature in fahrenheit.
            self._temperature = float(self.mygogogate2.get_temperature(self.device_id))
            if self._temp_unit == TEMP_CELSIUS:
                # Convert the output to celcius.
                self._temperature = (self._temperature - 32.0) * 5.0 / 9.0
        except (TypeError, KeyError, NameError, ValueError) as ex:
            _LOGGER.error("%s", ex)
            self._temperature = None
