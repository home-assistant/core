"""Constants for the AirPatrol integration."""

from datetime import timedelta
import logging

from airpatrol.api import AirPatrolAuthenticationError, AirPatrolError

from homeassistant.const import Platform

DOMAIN = "airpatrol"

LOGGER = logging.getLogger(__package__)
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=1)

AIRPATROL_ERRORS = (AirPatrolAuthenticationError, AirPatrolError)
