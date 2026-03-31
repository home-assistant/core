"""Constants for the Forecast.Solar integration."""

from __future__ import annotations

import logging

DOMAIN = "forecast_solar"
LOGGER = logging.getLogger(__package__)

CONF_ADJ = "adjustable"
CONF_AZIMUTH = "azimuth"
CONF_AZIMUTH_CHOICE = "azimuth_choice"
CONF_AZIMUTH_SENSOR = "azimuth_sensor"
CONF_DAMPING = "damping"
CONF_DAMPING_EVENING = "damping_evening"
CONF_DAMPING_MORNING = "damping_morning"
CONF_DECLINATION = "declination"
CONF_DECLINATION_CHOICE = "declination_choice"
CONF_DECLINATION_SENSOR = "declination_sensor"
CONF_FIXED = "fixed"
CONF_HOME_LOCATION = "home_location"
CONF_INVERTER_SIZE = "inverter_size"
CONF_LOCATION_CHOICE = "location_choice"
CONF_MANUAL_LOCATION = "manual_location"
CONF_MODULES_POWER = "modules_power"

AZIMUTH_MIN = 0
AZIMUTH_MAX = 360

DECLINATION_MIN = 0
DECLINATION_MAX = 90
