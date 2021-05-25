"""Consts used by SeventeenTrack."""
from typing import Final

DOMAIN: Final = "seventeentrack"

DEFAULT_NAME: Final = "SeventeenTrack"
DEFAULT_SCAN_INTERVAL: Final = 10

CONF_ACCOUNT = "account"
CONF_TRACKING_NUMBER: Final = "tracking_number"

SERVICE_ADD_PACKAGE: Final = "add_package"

ATTR_DESTINATION_COUNTRY: Final = "destination_country"
ATTR_INFO_TEXT: Final = "info_text"
ATTR_TIMESTAMP: Final = "timestamp"
ATTR_ORIGIN_COUNTRY: Final = "origin_country"
ATTR_PACKAGES: Final = "packages"
ATTR_PACKAGE_TYPE: Final = "package_type"
ATTR_STATUS: Final = "status"
ATTR_TRACKING_INFO_LANGUAGE: Final = "tracking_info_language"


ATTRIBUTION: Final = "Data provided by 17track.net"

ICON: Final = "mdi:package"
