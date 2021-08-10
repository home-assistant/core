"""Support for an exposed aREST RESTful API of a device."""

import logging

import requests
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_NAME, CONF_RESOURCE, HTTP_OK
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_FUNCTIONS = "functions"
CONF_PINS = "pins"
CONF_INVERT = "invert"

DEFAULT_NAME = "aREST switch"

PIN_FUNCTION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_INVERT, default=False): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PINS, default={}): vol.Schema(
            {cv.string: PIN_FUNCTION_SCHEMA}
        ),
        vol.Optional(CONF_FUNCTIONS, default={}): vol.Schema(
            {cv.string: PIN_FUNCTION_SCHEMA}
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the aREST switches."""
    resource = config[CONF_RESOURCE]

    try:
        response = requests.get(resource, timeout=10)
    except requests.exceptions.MissingSchema:
        _LOGGER.error(
            "Missing resource or schema in configuration. Add http:// to your URL"
        )
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s", resource)
        return False

    dev = []
    pins = config[CONF_PINS]
    for pinnum, pin in pins.items():
        dev.append(
            ArestSwitchPin(
                resource,
                config.get(CONF_NAME, response.json()[CONF_NAME]),
                pin.get(CONF_NAME),
                pinnum,
                pin[CONF_INVERT],
            )
        )

    functions = config[CONF_FUNCTIONS]
    for funcname, func in functions.items():
        dev.append(
            ArestSwitchFunction(
                resource,
                config.get(CONF_NAME, response.json()[CONF_NAME]),
                func.get(CONF_NAME),
                funcname,
            )
        )

    add_entities(dev)


class ArestSwitchBase(SwitchEntity):
    """Representation of an aREST switch."""

    def __init__(self, resource, location, name):
        """Initialize the switch."""
        self._resource = resource
        self._attr_name = f"{location.title()} {name.title()}"
        self._attr_available = True


class ArestSwitchFunction(ArestSwitchBase):
    """Representation of an aREST switch."""

    def __init__(self, resource, location, name, func):
        """Initialize the switch."""
        super().__init__(resource, location, name)
        self._func = func

        request = requests.get(f"{self._resource}/{self._func}", timeout=10)

        if request.status_code != HTTP_OK:
            _LOGGER.error("Can't find function")
            return

        try:
            request.json()["return_value"]
        except KeyError:
            _LOGGER.error("No return_value received")
        except ValueError:
            _LOGGER.error("Response invalid")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        request = requests.get(
            f"{self._resource}/{self._func}", timeout=10, params={"params": "1"}
        )

        if request.status_code == HTTP_OK:
            self._attr_is_on = True
        else:
            _LOGGER.error("Can't turn on function %s at %s", self._func, self._resource)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        request = requests.get(
            f"{self._resource}/{self._func}", timeout=10, params={"params": "0"}
        )

        if request.status_code == HTTP_OK:
            self._attr_is_on = False
        else:
            _LOGGER.error(
                "Can't turn off function %s at %s", self._func, self._resource
            )

    def update(self):
        """Get the latest data from aREST API and update the state."""
        try:
            request = requests.get(f"{self._resource}/{self._func}", timeout=10)
            self._attr_is_on = request.json()["return_value"] != 0
            self._attr_available = True
        except requests.exceptions.ConnectionError:
            _LOGGER.warning("No route to device %s", self._resource)
            self._attr_available = False


class ArestSwitchPin(ArestSwitchBase):
    """Representation of an aREST switch. Based on digital I/O."""

    def __init__(self, resource, location, name, pin, invert):
        """Initialize the switch."""
        super().__init__(resource, location, name)
        self._pin = pin
        self.invert = invert

        request = requests.get(f"{resource}/mode/{pin}/o", timeout=10)
        if request.status_code != HTTP_OK:
            _LOGGER.error("Can't set mode")
            self._attr_available = False

    def turn_on(self, **kwargs):
        """Turn the device on."""
        turn_on_payload = int(not self.invert)
        request = requests.get(
            f"{self._resource}/digital/{self._pin}/{turn_on_payload}", timeout=10
        )
        if request.status_code == HTTP_OK:
            self._attr_is_on = True
        else:
            _LOGGER.error("Can't turn on pin %s at %s", self._pin, self._resource)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        turn_off_payload = int(self.invert)
        request = requests.get(
            f"{self._resource}/digital/{self._pin}/{turn_off_payload}", timeout=10
        )
        if request.status_code == HTTP_OK:
            self._attr_is_on = False
        else:
            _LOGGER.error("Can't turn off pin %s at %s", self._pin, self._resource)

    def update(self):
        """Get the latest data from aREST API and update the state."""
        try:
            request = requests.get(f"{self._resource}/digital/{self._pin}", timeout=10)
            status_value = int(self.invert)
            self._attr_is_on = request.json()["return_value"] != status_value
            self._attr_available = True
        except requests.exceptions.ConnectionError:
            _LOGGER.warning("No route to device %s", self._resource)
            self._attr_available = False
