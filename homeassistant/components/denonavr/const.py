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

# Shared by both DenonAvrDataUpdateCoordinator instances (general status
# and Audyssey) - matches media_player.py's existing poll rate, since
# the general one replaces what media_player.py already polled at this
# interval, and there's no reason for Audyssey to be checked more often.
COORDINATOR_UPDATE_INTERVAL = 10

# Debounce for action-triggered refreshes specifically (not the
# recurring poll above, which is unaffected by this). Matches the
# established pattern for exactly this situation (see e.g. tplink's own
# coordinator): immediate=False rather than a plain
# async_request_refresh(), since the receiver needs a moment to settle
# after a command anyway, so waiting a short beat before confirming is
# correct, not just tolerated - and it coalesces near-simultaneous
# actions (e.g. two Audyssey-scoped settings changed in quick
# succession) into a single shared refresh instead of one each.
ACTION_REFRESH_DEBOUNCE_COOLDOWN = 0.5

# denonavr.const has no "list of valid options" helper for these three
# (unlike reference_level_offset/dynamic_volume/multi_eq); their option
# lists are fixed Literal types, reproduced here in the same order.
ECO_MODE_OPTIONS = ("On", "Auto", "Off")
DIMMER_OPTIONS = ("Off", "Dark", "Dim", "Bright")
AUTO_STANDBY_OPTIONS = ("OFF", "15M", "30M", "60M", "2H", "4H", "8H")
