"""Constants for the Netgear LTE integration."""
import logging
from typing import Final

ATTR_HOST = "host"
ATTR_SMS_ID = "sms_id"
ATTR_FROM = "from"
ATTR_MESSAGE = "message"
ATTR_FAILOVER = "failover"
ATTR_AUTOCONNECT = "autoconnect"
AUTOCONNECT_MODES = ["never", "home", "always"]

CONF_BINARY_SENSOR: Final = "binary_sensor"
CONF_NOTIFY: Final = "notify"
CONF_SENSOR: Final = "sensor"

DISPATCHER_NETGEAR_LTE = "netgear_lte_update"
DOMAIN: Final = "netgear_lte"

FAILOVER_MODES = ["auto", "wire", "mobile"]

LOGGER = logging.getLogger(__package__)
