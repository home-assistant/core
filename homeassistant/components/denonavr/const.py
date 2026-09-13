"""Constants for Denon AVR."""

DOMAIN = "denonavr"

ATTR_DYNAMIC_EQ = "dynamic_eq"

CONF_SHOW_ALL_SOURCES = "show_all_sources"
CONF_ZONE2 = "zone2"
CONF_ZONE3 = "zone3"
CONF_MANUFACTURER = "manufacturer"
CONF_SERIAL_NUMBER = "serial_number"
CONF_UPDATE_AUDYSSEY = "update_audyssey"
CONF_USE_TELNET = "use_telnet"

DEFAULT_SHOW_SOURCES = False
DEFAULT_TIMEOUT = 5
DEFAULT_ZONE2 = False
DEFAULT_ZONE3 = False
DEFAULT_UPDATE_AUDYSSEY = False
DEFAULT_USE_TELNET = False

# How long an optimistic pending select/switch value is trusted over
# the receiver's own reported value, in seconds. Comfortably above the
# documented worst case (~10s) for the slowest refresh (GetAudyssey).
PENDING_VALUE_TIMEOUT = 15

# Poll interval for the select/switch entities in this integration.
# Longer than the default (~15s) since several of them share the same
# underlying refresh call (e.g. three selects all trigger GetAudyssey);
# a longer interval keeps that redundancy from adding up to frequent
# receiver traffic while still letting external changes (made outside
# HA) surface without depending on the media player entity staying
# enabled.
ENTITY_SCAN_INTERVAL = 60

# denonavr.const has no "list of valid options" helper for these three
# (unlike reference_level_offset/dynamic_volume/multi_eq); their option
# lists are fixed Literal types, reproduced here in the same order.
ECO_MODE_OPTIONS = ("On", "Auto", "Off")
DIMMER_OPTIONS = ("Off", "Dark", "Dim", "Bright")
AUTO_STANDBY_OPTIONS = ("OFF", "15M", "30M", "60M", "2H", "4H", "8H")
