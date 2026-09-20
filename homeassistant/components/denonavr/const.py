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

# Seconds an optimistic pending value is trusted over the receiver's own,
# comfortably above the ~10s worst case documented for the slowest refresh.
PENDING_VALUE_TIMEOUT = 15

# Shared by both coordinators, at the rate media_player.py polls at.
COORDINATOR_UPDATE_INTERVAL = 10

# Delay action-triggered refreshes so the receiver can settle and coalesce changes.
ACTION_REFRESH_DEBOUNCE_COOLDOWN = 0.5

# denonavr.const offers no list helper for these three, only a Literal type,
# so the options are reproduced here in the same order.
ECO_MODE_OPTIONS = ("On", "Auto", "Off")
DIMMER_OPTIONS = ("Off", "Dark", "Dim", "Bright")
AUTO_STANDBY_OPTIONS = ("OFF", "15M", "30M", "60M", "2H", "4H", "8H")

# Telnet event group carrying all Audyssey settings (DYNEQ, MULTEQ,
# REFLEV, DYNVOL) - used by __init__.py to notify the Audyssey
# coordinator independently of whether the media_player entity is enabled.
AUDYSSEY_TELNET_EVENT = "PS"

# Telnet events relevant to media_player.py's own state.
TELNET_EVENTS = {
    "HD",
    "MS",
    "MU",
    "MV",
    "NS",
    "NSE",
    "PS",
    "SI",
    "SS",
    "TF",
    "ZM",
    "Z2",
    "Z3",
}
