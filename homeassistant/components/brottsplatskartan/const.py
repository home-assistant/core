"""Adds constants for brottsplatskartan integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "brottsplatskartan"
PLATFORMS = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

CONF_AREA = "area"
CONF_APP_ID = "app_id"
DEFAULT_NAME = "Brottsplatskartan"
