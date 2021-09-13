"""Constants for the WattTime integration."""
import logging

DOMAIN = "watttime"

LOGGER = logging.getLogger(__package__)

AUTH_TYPE_LOGIN = "Login with an existing username"
AUTH_TYPE_REGISTER = "Register a new username"

CONF_BALANCING_AUTHORITY = "balancing_authority"
CONF_BALANCING_AUTHORITY_ABBREV = "balancing_authority_abbreviation"

DATA_COORDINATOR = "coordinator"
