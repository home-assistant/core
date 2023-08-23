"""Adds constants for Trafikverket Camera integration."""
from homeassistant.const import Platform

DOMAIN = "trafikverket_camera"
CONF_LOCATION = "location"
PLATFORMS = [Platform.CAMERA]
ATTRIBUTION = "Data provided by Trafikverket"

ATTR_DESCRIPTION = "description"
ATTR_TYPE = "type"
