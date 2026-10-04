"""Constants for the Prowl Notification service."""

from homeassistant.const import Platform

DOMAIN = "prowl"
PLATFORMS = [Platform.NOTIFY]

CONF_ENTRY = "entry"
# Set on entries imported from YAML; holds the YAML names of the legacy notify services
CONF_LEGACY_SERVICE_NAMES = "legacy_service_names"
