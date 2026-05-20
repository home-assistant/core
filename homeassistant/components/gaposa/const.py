"""Constants for the Gaposa integration."""

DOMAIN = "gaposa"
DEFAULT_GATEWAY_NAME = "Gaposa Gateway"

# Motor state strings returned by pygaposa's Motor.state attribute.
# These map directly onto the values the Gaposa cloud emits.
STATE_UP = "UP"
STATE_DOWN = "DOWN"

# Command strings recorded on a cover entity to remember what the
# last user-initiated action was. They are compared in is_opening /
# is_closing to decide whether the cover should report as moving.
COMMAND_UP = "UP"
COMMAND_DOWN = "DOWN"
COMMAND_STOP = "STOP"

# Seconds between coordinator refreshes during normal operation and
# after a transient failure, respectively. The fast interval lets the
# integration recover quickly from a blip without hammering the API.
UPDATE_INTERVAL = 600
UPDATE_INTERVAL_FAST = 60

# Seconds a cover entity reports as "opening"/"closing" after an
# open/close command is issued. Gaposa's cloud API does not report
# motion state directly, so we approximate it from the time the
# command was sent.
MOTION_DELAY = 60
