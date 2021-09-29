"""Amber Electric Constants."""
import logging

DOMAIN = "amberelectric"
CONF_API_TOKEN = "api_token"
CONF_SITE_NAME = "site_name"
CONF_SITE_ID = "site_id"
CONF_SITE_NMI = "site_nmi"

ATTRIBUTION = "Data provided by Amber Electric"

LOGGER = logging.getLogger(__package__)
PLATFORMS = ["sensor", "binary_sensor"]
