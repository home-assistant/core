"""Constants for the Forecast.Solar integration."""
from __future__ import annotations

import logging

DOMAIN = "forecast_solar"
LOGGER = logging.getLogger(__package__)

CONF_DECLINATION = "declination"
CONF_DECLINATION_SENSOR = "declination_sensor"
CONF_AZIMUTH = "azimuth"
CONF_AZIMUTH_SENSOR = "azimuth_sensor"
CONF_MODULES_POWER = "modules_power"
CONF_DAMPING = "damping"
CONF_DAMPING_MORNING = "damping_morning"
CONF_DAMPING_EVENING = "damping_evening"
CONF_INVERTER_SIZE = "inverter_size"
CONF_HOME_LOCATION = "home_location"
CONF_LOCATION_CHOICE = "location_choice"
CONF_LOCATION_ZONE = "location_zone"
CONF_MANUAL_LOCATION = "manual_location"
CONF_AZIMUTH_CHOICE = "azimuth_choice"
CONF_FIXED = "fixed"
CONF_ADJ = "adjustable"
CONF_DECLINATION_CHOICE = "declination_choice"
