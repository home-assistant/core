"""The Philips TV constants."""

DOMAIN = "philips_js"
CONF_SYSTEM = "system"
CONF_ALLOW_NOTIFY = "allow_notify"

# Seconds a TV that stopped answering keeps its last known state.
UNREACHABLE_GRACE = 180
# Seconds a command waits for a TV that does not answer yet.
WAKE_TIMEOUT = 20

CONST_APP_ID = "homeassistant.io"
CONST_APP_NAME = "Home Assistant"

TV_STATE_OFF = "Off"
TV_STATE_ON = "On"

TRIGGER_TYPE_TURN_ON = "turn_on"
