"""Constants for the Forecast.Solar integration."""
from __future__ import annotations

import logging

DOMAIN = "forecast_solar"
LOGGER = logging.getLogger(__package__)

CONF_DECLINATION = "declination"
CONF_AZIMUTH = "azimuth"
CONF_MODULES_POWER = "modules power"
CONF_DAMPING = "damping"
CONF_INVERTER_SIZE = "inverter_size"
