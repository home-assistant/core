"""Constants for the 17track.net component."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

ATTR_DESTINATION_COUNTRY = "destination_country"
ATTR_INFO_TEXT = "info_text"
ATTR_TIMESTAMP = "timestamp"
ATTR_ORIGIN_COUNTRY = "origin_country"
ATTR_PACKAGES = "packages"
ATTR_PACKAGE_TYPE = "package_type"
ATTR_STATUS = "status"
ATTR_TRACKING_INFO_LANGUAGE = "tracking_info_language"
ATTR_TRACKING_NUMBER = "tracking_number"

CONF_SHOW_ARCHIVED = "show_archived"
CONF_SHOW_DELIVERED = "show_delivered"

DEFAULT_SHOW_ARCHIVED = False
DEFAULT_SHOW_DELIVERED = False

DOMAIN = "seventeentrack"

DATA_PACKAGES = "package_data"
DATA_SUMMARY = "summary_data"

ATTRIBUTION = "Data provided by 17track.net"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

UNIQUE_ID_TEMPLATE = "package_{0}_{1}"
ENTITY_ID_TEMPLATE = "sensor.seventeentrack_package_{0}"

NOTIFICATION_DELIVERED_ID = "package_delivered_{0}"
NOTIFICATION_DELIVERED_TITLE = "Package {0} delivered"
NOTIFICATION_DELIVERED_MESSAGE = (
    "Package Delivered: {0}<br />Visit 17.track for more information: "
    "https://t.17track.net/track#nums={1}"
)

VALUE_DELIVERED = "Delivered"

SERVICE_GET_PACKAGES = "get_packages"

ATTR_PACKAGE_STATE = "package_state"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

DEPRECATED_KEY = "deprecated"
