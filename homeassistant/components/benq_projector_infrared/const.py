"""Constants for the BenQ Projector Infrared integration."""

from datetime import timedelta
from enum import StrEnum

DOMAIN = "benq_projector_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_WARM_UP_TIME = "warm_up_time"
CONF_COOL_DOWN_TIME = "cool_down_time"
DEVICE_NAME = "BenQ projector"

# The projector ignores every command while it warms up or cools down.
DEFAULT_WARM_UP_TIME = 60
DEFAULT_COOL_DOWN_TIME = 60

# The projector only powers off when the off command is confirmed by a second one.
POWER_OFF_CONFIRM_DELAY = 1.0
POWER_OFF_CONFIRM_WINDOW = timedelta(seconds=4)


class BenQProjectorBusyReason(StrEnum):
    """Why the projector ignores commands."""

    WARMING_UP = "warming_up"
    COOLING_DOWN = "cooling_down"
