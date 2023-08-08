"""The enphase_envoy component."""
from pyenphase import (
    EnvoyAuthenticationError,
    EnvoyAuthenticationRequired,
)

from homeassistant.const import Platform

DOMAIN = "enphase_envoy"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

INVALID_AUTH_ERRORS = (EnvoyAuthenticationError, EnvoyAuthenticationRequired)
