"""The enphase_envoy component."""

from pyenphase import EnvoyAuthenticationError, EnvoyAuthenticationRequired

from homeassistant.const import Platform

DOMAIN = "enphase_envoy"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

INVALID_AUTH_ERRORS = (EnvoyAuthenticationError, EnvoyAuthenticationRequired)

OPTION_DIAGNOSTICS_INCLUDE_FIXTURES = "diagnostics_include_fixtures"
OPTION_DIAGNOSTICS_INCLUDE_FIXTURES_DEFAULT_VALUE = False
