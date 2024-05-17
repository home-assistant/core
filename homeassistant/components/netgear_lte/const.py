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

DATA_HASS_CONFIG = "netgear_lte_hass_config"
# https://kb.netgear.com/31160/How-do-I-change-my-4G-LTE-Modem-s-IP-address-range
DEFAULT_HOST = "192.168.5.1"
DISPATCHER_NETGEAR_LTE = "netgear_lte_update"
DOMAIN: Final = "netgear_lte"

FAILOVER_MODES = ["auto", "wire", "mobile"]

LOGGER = logging.getLogger(__package__)

MANUFACTURER: Final = "Netgear"
