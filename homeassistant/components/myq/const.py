"""The MyQ integration."""
from pymyq.garagedoor import (
    STATE_CLOSED as MYQ_COVER_STATE_CLOSED,
    STATE_CLOSING as MYQ_COVER_STATE_CLOSING,
    STATE_OPEN as MYQ_COVER_STATE_OPEN,
    STATE_OPENING as MYQ_COVER_STATE_OPENING,
)
from pymyq.lamp import STATE_OFF as MYQ_LIGHT_STATE_OFF, STATE_ON as MYQ_LIGHT_STATE_ON

from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
)

DOMAIN = "myq"

PLATFORMS = ["cover", "binary_sensor", "light"]

MYQ_TO_HASS = {
    MYQ_COVER_STATE_CLOSED: STATE_CLOSED,
    MYQ_COVER_STATE_CLOSING: STATE_CLOSING,
    MYQ_COVER_STATE_OPEN: STATE_OPEN,
    MYQ_COVER_STATE_OPENING: STATE_OPENING,
    MYQ_LIGHT_STATE_ON: STATE_ON,
    MYQ_LIGHT_STATE_OFF: STATE_OFF,
}

MYQ_GATEWAY = "myq_gateway"
MYQ_COORDINATOR = "coordinator"

# myq has some ratelimits in place
# and 61 seemed to be work every time
UPDATE_INTERVAL = 15

# Estimated time it takes myq to start transition from one
# state to the next.
TRANSITION_START_DURATION = 7

# Estimated time it takes myq to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 37
