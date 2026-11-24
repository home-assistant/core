"""Constants for the BenQ Projector Infrared integration."""

from datetime import timedelta

DOMAIN = "benq_projector_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
DEVICE_NAME = "BenQ projector"

# The projector only powers off when the off command is confirmed by a second one.
POWER_OFF_CONFIRM_DELAY = 1.0
POWER_OFF_CONFIRM_WINDOW = timedelta(seconds=4)
