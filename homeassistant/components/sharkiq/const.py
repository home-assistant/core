"""Shark IQ Constants."""
from datetime import timedelta
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

API_TIMEOUT = 20
PLATFORMS = [Platform.VACUUM]
DOMAIN = "sharkiq"
SHARK = "Shark"
UPDATE_INTERVAL = timedelta(seconds=30)

SHARKIQ_REGION_EUROPE = "europe"
SHARKIQ_REGION_ELSEWHERE = "elsewhere"
SHARKIQ_REGION_DEFAULT = SHARKIQ_REGION_ELSEWHERE
SHARKIQ_REGION_OPTIONS = [SHARKIQ_REGION_EUROPE, SHARKIQ_REGION_ELSEWHERE]
