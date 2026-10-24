"""Constants for the GTFS integration."""

from homeassistant.util.hass_dict import HassKey

DOMAIN = "gtfs"

FLOW_DATABASES: HassKey[set[str]] = HassKey(f"{DOMAIN}_flow_databases")

CONF_DATA = "data"
CONF_DATABASE = "database"
CONF_DESTINATION = "destination"
CONF_ORIGIN = "origin"
CONF_TOMORROW = "include_tomorrow"

DEFAULT_PATH = "gtfs"

SUBENTRY_TYPE_ROUTE = "route"
