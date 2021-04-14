"""Constants used in the Keenetic NDMS2 components."""

from homeassistant.components.device_tracker.const import (
    DEFAULT_CONSIDER_HOME as _DEFAULT_CONSIDER_HOME,
)

DOMAIN = "keenetic_ndms2"
ROUTER = "router"
UNDO_UPDATE_LISTENER = "undo_update_listener"
DEFAULT_TELNET_PORT = 23
DEFAULT_SCAN_INTERVAL = 120
DEFAULT_CONSIDER_HOME = _DEFAULT_CONSIDER_HOME.seconds
DEFAULT_INTERFACE = "Home"

CONF_CONSIDER_HOME = "consider_home"
CONF_INTERFACES = "interfaces"
CONF_TRY_HOTSPOT = "try_hotspot"
CONF_INCLUDE_ARP = "include_arp"
CONF_INCLUDE_ASSOCIATED = "include_associated"

CONF_LEGACY_INTERFACE = "interface"
