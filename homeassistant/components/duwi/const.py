"""Constants for the Duwi integration.

This module contains constants that are used throughout the Duwi Smart Hub integration,
including configuration keys, default values, and URLs for API endpoints.
"""

from homeassistant.const import Platform

# Unique domain identifier for the Duwi Smart Hub integration
DOMAIN = "duwi"

# Manufacturer of the product for identification purposes
MANUFACTURER = "Duwi"

# Version of the App for the Duwi Smart Hub integration, used for tracking and compatibility.
APP_VERSION = "0.1.1"

# Home Assistant client version
CLIENT_VERSION = "0.1.1"

# Model identification of the Home Assistant client, typically used for logging or diagnostics.
CLIENT_MODEL = "homeassistant"

# List of platforms that support config entry
SUPPORTED_PLATFORMS = [Platform.SWITCH]

SENSOR_TYPE = "7"
