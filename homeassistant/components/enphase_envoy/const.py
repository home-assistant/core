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

OPTION_DISABLE_KEEP_ALIVE = "disable_keep_alive"
OPTION_DISABLE_KEEP_ALIVE_DEFAULT_VALUE = False
