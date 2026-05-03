"""Compensation constants."""

from typing import Any

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN = "compensation"
PLATFORMS = [Platform.SENSOR]

SENSOR = "compensation"

CONF_COMPENSATION = "compensation"
CONF_LOWER_LIMIT = "lower_limit"
CONF_UPPER_LIMIT = "upper_limit"
CONF_DATAPOINTS = "data_points"
CONF_DEGREE = "degree"
CONF_PRECISION = "precision"
CONF_POLYNOMIAL = "polynomial"
CONF_POLYNOMIAL_CONFIG = "polynomial_config"


DATA_COMPENSATION: HassKey[dict[str, Any]] = HassKey("compensation_data")

DEFAULT_DEGREE = 1
DEFAULT_NAME = "Compensation"
DEFAULT_PRECISION = 2
