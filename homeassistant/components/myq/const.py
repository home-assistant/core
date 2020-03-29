"""The MyQ integration."""
from pymyq.device import (
    STATE_CLOSED as MYQ_STATE_CLOSED,
    STATE_CLOSING as MYQ_STATE_CLOSING,
    STATE_OPEN as MYQ_STATE_OPEN,
    STATE_OPENING as MYQ_STATE_OPENING,
)

from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

DOMAIN = "myq"

PLATFORMS = ["cover"]

MYQ_DEVICE_TYPE = "device_type"
MYQ_DEVICE_TYPE_GATE = "gate"
MYQ_DEVICE_STATE = "state"
MYQ_DEVICE_STATE_ONLINE = "online"


MYQ_TO_HASS = {
    MYQ_STATE_CLOSED: STATE_CLOSED,
    MYQ_STATE_CLOSING: STATE_CLOSING,
    MYQ_STATE_OPEN: STATE_OPEN,
    MYQ_STATE_OPENING: STATE_OPENING,
}

MYQ_GATEWAY = "myq_gateway"
MYQ_COORDINATOR = "coordinator"

# myq has some ratelimits in place
# and 61 seemed to be work every time
UPDATE_INTERVAL = 61

# Estimated time it takes myq to start transition from one
# state to the next.
TRANSITION_START_DURATION = 7

# Estimated time it takes myq to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 37
