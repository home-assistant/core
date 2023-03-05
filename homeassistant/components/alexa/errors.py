"""Alexa related errors."""
from __future__ import annotations

from typing import Literal

from homeassistant.exceptions import HomeAssistantError

from .const import API_TEMP_UNITS


class UnsupportedProperty(HomeAssistantError):
    """Does not support the requested Smart Home API property."""


class NoTokenAvailable(HomeAssistantError):
    """There is no access token available."""


class RequireRelink(Exception):
    """The skill needs to be relinked."""


class AlexaError(Exception):
    """Base class for errors that can be serialized for the Alexa API.

    A handler can raise subclasses of this to return an error to the request.
    """

    namespace: str | None = None
    error_type: str | None = None

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
        msg = f"The endpoint {endpoint_id} does not exist"
        AlexaError.__init__(self, msg)
        self.endpoint_id = endpoint_id


class AlexaInvalidValueError(AlexaError):
    """Class to represent InvalidValue errors."""

    namespace = "Alexa"
    error_type = "INVALID_VALUE"


class AlexaInteralError(AlexaError):
    """Class to represent internal errors."""

    namespace = "Alexa"
    error_type = "INTERNAL_ERROR"


class AlexaNotSupportedInCurrentMode(AlexaError):
    """The device is not in the correct mode to support this command."""

    namespace = "Alexa"
    error_type = "NOT_SUPPORTED_IN_CURRENT_MODE"

    def __init__(
        self,
        endpoint_id: str,
        current_mode: Literal["COLOR", "ASLEEP", "NOT_PROVISIONED", "OTHER"],
    ) -> None:
        """Initialize invalid endpoint error."""
        msg = f"Not supported while in {current_mode} mode"
        AlexaError.__init__(self, msg, {"currentDeviceMode": current_mode})
        self.endpoint_id = endpoint_id


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
        msg = f"The requested temperature {temp} is out of range"

        AlexaError.__init__(self, msg, payload)


class AlexaBridgeUnreachableError(AlexaError):
    """Class to represent BridgeUnreachable errors."""

    namespace = "Alexa"
    error_type = "BRIDGE_UNREACHABLE"


class AlexaSecurityPanelUnauthorizedError(AlexaError):
    """Class to represent SecurityPanelController Unauthorized errors."""

    namespace = "Alexa.SecurityPanelController"
    error_type = "UNAUTHORIZED"


class AlexaSecurityPanelAuthorizationRequired(AlexaError):
    """Class to represent SecurityPanelController AuthorizationRequired errors."""

    namespace = "Alexa.SecurityPanelController"
    error_type = "AUTHORIZATION_REQUIRED"


class AlexaAlreadyInOperationError(AlexaError):
    """Class to represent AlreadyInOperation errors."""

    namespace = "Alexa"
    error_type = "ALREADY_IN_OPERATION"


class AlexaInvalidDirectiveError(AlexaError):
    """Class to represent InvalidDirective errors."""

    namespace = "Alexa"
    error_type = "INVALID_DIRECTIVE"


class AlexaVideoActionNotPermittedForContentError(AlexaError):
    """Class to represent action not permitted for content errors."""

    namespace = "Alexa.Video"
    error_type = "ACTION_NOT_PERMITTED_FOR_CONTENT"
