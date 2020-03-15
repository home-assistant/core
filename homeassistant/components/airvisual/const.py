"""Define AirVisual constants."""
import logging

DOMAIN = "airvisual"
LOGGER = logging.getLogger("homeassistant.components.airvisual")

INTEGRATION_TYPE_GEOGRAPHY = "Geographical Location"
INTEGRATION_TYPE_NODE_PRO = "AirVisual Node/Pro"

CONF_CITY = "city"
CONF_COUNTRY = "country"
CONF_GEOGRAPHIES = "geographies"

DATA_CLIENT = "client"

TOPIC_UPDATE = f"airvisual_update_{0}"
