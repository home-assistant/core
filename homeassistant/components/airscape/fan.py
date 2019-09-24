"""Platform for Airscape fan integration."""
import logging

import airscape
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.fan import SUPPORT_SET_SPEED, PLATFORM_SCHEMA, FanEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_MINIMUM, ATTR_ENTITY_ID
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

DEFAULT_TIMEOUT = 5
DEFAULT_MINIMUM = 1

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_MINIMUM, default=DEFAULT_MINIMUM): cv.positive_int,
    }
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.string,
    }
)

SIGNAL_AIRSCAPE_SPEEDUP = "airscape_{}_speedup"
SIGNAL_AIRSCAPE_SLOWDOWN = "airscape_{}_slowdown"

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Airscape Fan platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = config[CONF_HOST]
    name = config[CONF_NAME]
    minimum = config[CONF_MINIMUM]

    try:
        device = airscape.Fan(host, timeout)
    except (airscape.exceptions.Timeout, airscape.exceptions.ConnectionError):
        _LOGGER.error(
            "Cannot connect to %s.  " "Device did not respond to API request", host
        )
    else:
        # Add devices
        add_entities([AirscapeWHF(device, name, minimum)], True)

    def handle_speed_up(call):
        """Handle speed_up service call."""
        entity_id = call.data[]"entity_id"]
        _LOGGER.debug("Calling speed_up for %s", entity_id)
        async_dispatcher_send(hass, SIGNAL_AIRSCAPE_SPEEDUP.format(entity_id))

        
    def handle_slow_down(call):
        """Handle slow_down service call."""
        entity_id = call.data.get("entity_id")
        _LOGGER.debug("Calling slow_down for %s", entity_id)
        async_dispatcher_send(hass, SIGNAL_AIRSCAPE_SLOWDOWN.format(entity_id))
        
    hass.services.register(DOMAIN, "speed_up", handle_speed_up, SERVICE_SCHEMA)
    hass.services.register(DOMAIN, "slow_down", handle_slow_down, SERVICE_SCHEMA)


class AirscapeWHF(FanEntity):
    """Representation of an Airscape Fan."""

    def __init__(self, device, name, minimum):
        """Initialize a AirscapeFan."""
        self._fan = device
        self._name = name
        self._state = None
        self._speed = None
        self._available = True
        self._minimum_speed = minimum
        self._speed_list = [f"{i}" for i in range(0, 11)]

    def async_added_to_hass(self):
        """Register dispatcher connections"""
        async_dispatcher_connect(self.hass, SIGNAL_AIRSCAPE_SPEEDUP.format(self.entity_id), speed_up)
        async_dispatcher_connect(self.hass, SIGNAL_AIRSCAPE_SLOWDOWN.format(self.entity_id), slow_down)

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._name

    @property
    def available(self):
        """Return if device is available."""
        return self._available

    @property
    def supported_features(self):
        """Return supported features of fan."""
        return SUPPORT_SET_SPEED

    @property
    def is_on(self):
        """Return state of fan."""
        return self._state

    def turn_on(self, speed: str = None, **kwargs):
        """Instruct the fan to turn on."""
        try:
            if speed is not None:
                self._fan.speed = int(speed)
            else:
                self._fan.speed = int(self._minimum_speed)
        except (airscape.exceptions.ConnectionError, airscape.exceptions.Timeout):
            self._available = False

    def turn_off(self, **kwargs):
        """Instruct the fan to turn off."""
        try:
            self._fan.is_on = False
        except (airscape.exceptions.ConnectionError, airscape.exceptions.Timeout):
            self._available = False
            _LOGGER.error(
                "%s did not respond to command.  Not changing state.", self._name
            )

    def speed_up(self):
        """Instruct fan to increment speed up by 1."""
        try:
            self._fan.speed_up()
        except (airscape.exceptions.ConnectionError, airscape.exceptions.Timeout):
            self._available = False

    def slow_down(self):
        """Instruct fan to increment speed down by 1."""
        try:
            if int(self._speed) - 1 >= self._minimum_speed:
                self._fan.slow_down()
        except (airscape.exceptions.ConnectionError, airscape.exceptions.Timeout):
            self._available = False
            _LOGGER.error(
                "%s did not respond to command.  Not changing state.", self._name
            )

    @property
    def speed_list(self):
        """Return list of available speeds."""
        return self._speed_list

    @property
    def speed(self):
        """Return the speed of the fan."""
        return self._speed

    def set_speed(self, speed):
        """Set the speed of the fan."""
        if not bool(int(speed)):
            self._fan.is_on = False
        try:
            self._fan.speed = int(speed)
        except (airscape.exceptions.ConnectionError, airscape.exceptions.Timeout):
            self._available = False
            _LOGGER.error(
                "%s did not respond to command.  Not changing state.", self._name
            )

    def update(self):
        """Fetch new state data for this fan.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            fan_data = self._fan.get_device_state()
        except (airscape.exceptions.ConnectionError, airscape.exceptions.Timeout):
            self._available = False
            _LOGGER.error("Could not get state of %s", self._name)
        else:
            self._available = True
            self._state = bool(fan_data["fanspd"])
            self._speed = str(fan_data["fanspd"])
