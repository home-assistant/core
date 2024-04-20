"""Constants for the Forecast.Solar integration."""

from __future__ import annotations

import logging

DOMAIN = "forecast_solar"
LOGGER = logging.getLogger(__package__)

CONF_DECLINATION = "declination"
CONF_AZIMUTH = "azimuth"
CONF_MODULES_POWER = "modules_power"
CONF_DAMPING = "damping"
CONF_DAMPING_MORNING = "damping_morning"
CONF_DAMPING_EVENING = "damping_evening"
CONF_INVERTER_SIZE = "inverter_size"
