"""Adds constants for Trafikverket Train integration."""

from homeassistant.const import Platform

DOMAIN = "trafikverket_train"
PLATFORMS = [Platform.SENSOR]
ATTRIBUTION = "Data provided by Trafikverket"

CONF_FROM = "from"
CONF_TO = "to"
CONF_TIME = "time"
CONF_FILTER_PRODUCT = "filter_product"
