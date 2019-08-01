"""Alexa related errors."""
from homeassistant.exceptions import HomeAssistantError

from .const import API_TEMP_UNITS


class UnsupportedInterface(HomeAssistantError):
    """This entity does not support the requested Smart Home API interface."""


class UnsupportedProperty(HomeAssistantError):
    """This entity does not support the requested Smart Home API property."""


class NoTokenAvailable(HomeAssistantError):
    """There is no access token available."""


class AlexaError(Exception):
    """Base class for errors that can be serialized for the Alexa API.

    A handler can raise subclasses of this to return an error to the request.
    """

    namespace = None
    error_type = None

    def __init__(self, error_message, payload=None):
        """Initialize an alexa error."""
        Exception.__init__(self)
        self.error_message = error_message
        self.payload = None


class AlexaInvalidEndpointError(AlexaError):
    """The endpoint in the request does not exist."""

    namespace = "Alexa"
    error_type = "NO_SUCH_ENDPOINT"

    def __init__(self, endpoint_id):
        """Initialize invalid endpoint error."""
        msg = "The endpoint {} does not exist".format(endpoint_id)
        AlexaError.__init__(self, msg)
        self.endpoint_id = endpoint_id


class AlexaInvalidValueError(AlexaError):
    """Class to represent InvalidValue errors."""

    namespace = "Alexa"
    error_type = "INVALID_VALUE"


class AlexaUnsupportedThermostatModeError(AlexaError):
    """Class to represent UnsupportedThermostatMode errors."""

    namespace = "Alexa.ThermostatController"
    error_type = "UNSUPPORTED_THERMOSTAT_MODE"


class AlexaTempRangeError(AlexaError):
    """Class to represent TempRange errors."""

    namespace = "Alexa"
    error_type = "TEMPERATURE_VALUE_OUT_OF_RANGE"

    def __init__(self, hass, temp, min_temp, max_temp):
        """Initialize TempRange error."""
        unit = hass.config.units.temperature_unit
        temp_range = {
            "minimumValue": {"value": min_temp, "scale": API_TEMP_UNITS[unit]},
            "maximumValue": {"value": max_temp, "scale": API_TEMP_UNITS[unit]},
        }
        payload = {"validRange": temp_range}
        msg = "The requested temperature {} is out of range".format(temp)

        AlexaError.__init__(self, msg, payload)


class AlexaBridgeUnreachableError(AlexaError):
    """Class to represent BridgeUnreachable errors."""

    namespace = "Alexa"
    error_type = "BRIDGE_UNREACHABLE"
