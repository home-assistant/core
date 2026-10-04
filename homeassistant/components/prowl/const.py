"""Constants for the Prowl Notification service."""

from homeassistant.const import Platform

DOMAIN = "prowl"
PLATFORMS = [Platform.NOTIFY]

CONF_ENTRY = "entry"
# Set on entries imported from YAML; holds the YAML name of the legacy notify service
CONF_LEGACY_SERVICE_NAME = "legacy_service_name"
