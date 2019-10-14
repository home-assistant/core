"""Support for Gardena Smart system devices."""
import logging

from gardena.smart_system import SmartSystem
from oauthlib.oauth2.rfc6749.errors import (
    AccessDeniedError,
    InvalidClientError,
    MissingTokenError,
)
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "gardena"
GARDENA_SYSTEM = "gardena_system"
GARDENA_LOCATION = "gardena_location"
GARDENA_CONFIG = "gardena_config"
CONF_CLIENT_ID = "client_id"
CONF_LOCATION_ID = "location_id"
CONF_MOWER_DURATION = "mower_duration"
CONF_SMART_IRRIGATION_DURATION = "smart_irrigation_control_duration"
CONF_SMART_WATERING = "smart_watering_duration"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_LOCATION_ID): cv.string,
                vol.Optional(CONF_MOWER_DURATION, default="60"): cv.string,
                vol.Optional(CONF_SMART_IRRIGATION_DURATION, default="60"): cv.string,
                vol.Optional(CONF_SMART_WATERING, default="60"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


ATTR_NAME = "name"
ATTR_ACTIVITY = "activity"
ATTR_BATTERY_STATE = "battery_state"
ATTR_RF_LINK_LEVEL = "rf_link_level"
ATTR_RF_LINK_STATE = "rf_link_state"
ATTR_SERIAL = "serial"
ATTR_OPERATING_HOURS = "operating_hours"
ATTR_LAST_ERRORS = "last_error"


async def async_setup(hass, config):
    """Set up the Gardena integation."""
    _LOGGER.debug("Initialising Gardena")

    try:
        hass.data[GARDENA_SYSTEM] = GardenaSmartSystem(
            hass, config[DOMAIN], SmartSystem
        )
        hass.data[GARDENA_CONFIG] = config[DOMAIN]
        _LOGGER.debug("Gardena component initialised")
        for component in ("vacuum", "sensor", "switch"):
            hass.async_create_task(
                async_load_platform(hass, component, DOMAIN, {}, config)
            )

        return True
    except (AccessDeniedError, InvalidClientError, MissingTokenError) as exception:
        _LOGGER.error("Gardena component could not be initialised")
        print(exception)
        return False


class GardenaSmartSystem:
    """A Gardena Smart System wrapper class."""

    def __init__(self, hass, domain_config, smart_system):
        """Initialize the Gardena Smart System."""
        self.config = domain_config
        self._hass = hass

        self.smart_system = smart_system(
            domain_config[CONF_EMAIL],
            domain_config[CONF_PASSWORD],
            domain_config[CONF_CLIENT_ID],
        )
        self.smart_system.authenticate()
        self.smart_system.update_locations()
        self.smart_system.update_devices(
            self.smart_system.locations[domain_config[CONF_LOCATION_ID]]
        )
        self._hass.data[GARDENA_LOCATION] = self.smart_system.locations[
            domain_config[CONF_LOCATION_ID]
        ]
        self.smart_system.start_ws(self._hass.data[GARDENA_LOCATION])
