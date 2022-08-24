"""Adds constants for Trafikverket Ferry integration."""
from homeassistant.const import Platform

DOMAIN = "trafikverket_ferry"
PLATFORMS = [Platform.SENSOR]
ATTRIBUTION = "Data provided by Trafikverket"

CONF_TRAINS = "trains"
CONF_FROM = "from"
CONF_TO = "to"
CONF_TIME = "time"
