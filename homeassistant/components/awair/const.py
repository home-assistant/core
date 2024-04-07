"""Constants for the Awair component."""

from __future__ import annotations

from datetime import timedelta
import logging

API_CO2 = "carbon_dioxide"
API_DUST = "dust"
API_HUMID = "humidity"
API_LUX = "illuminance"
API_PM10 = "particulate_matter_10"
API_PM25 = "particulate_matter_2_5"
API_SCORE = "score"
API_SPL_A = "sound_pressure_level"
API_TEMP = "temperature"
API_TIMEOUT = 20
API_VOC = "volatile_organic_compounds"

ATTRIBUTION = "Awair air quality sensor"

DOMAIN = "awair"

LOGGER = logging.getLogger(__package__)

UPDATE_INTERVAL_CLOUD = timedelta(minutes=5)
UPDATE_INTERVAL_LOCAL = timedelta(seconds=30)
