"""Define AirVisual constants."""
import logging

DOMAIN = "airvisual"
LOGGER = logging.getLogger(__package__)

INTEGRATION_TYPE_GEOGRAPHY_COORDS = "Geographical Location by Latitude/Longitude"
INTEGRATION_TYPE_GEOGRAPHY_NAME = "Geographical Location by Name"
INTEGRATION_TYPE_NODE_PRO = "AirVisual Node/Pro"

CONF_CITY = "city"
CONF_GEOGRAPHIES = "geographies"
CONF_INTEGRATION_TYPE = "integration_type"
