"""Constants for the Homewizard integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "homewizard"
PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

LOGGER = logging.getLogger(__package__)

# Platform config.
CONF_API_ENABLED = "api_enabled"
CONF_DATA = "data"
CONF_PRODUCT_NAME = "product_name"
CONF_PRODUCT_TYPE = "product_type"
CONF_SERIAL = "serial"

UPDATE_INTERVAL = timedelta(seconds=5)
