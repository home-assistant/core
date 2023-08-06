"""The enphase_envoy component."""
from pyenphase import (
    EnvoyAuthenticationError,
    EnvoyAuthenticationRequired,
)

from homeassistant.const import Platform

DOMAIN = "enphase_envoy"

PLATFORMS = [Platform.SENSOR]

CONF_TOKEN = "token"

INVALID_AUTH_ERRORS = (EnvoyAuthenticationError, EnvoyAuthenticationRequired)
