"""Constants for the QConnex integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "klyqa"


CONF_POLLING = "polling"
CONF_SYNC_ROOMS = "sync_rooms"
EVENT_KLYQA_NEW_LIGHT = "klyqa_new_light"
EVENT_KLYQA_NEW_LIGHT_GROUP = "klyqa_new_light_group"
EVENT_KLYQA_NEW_VC = "klyqa_new_vc"

REQUEST_TIMEOUT = 11000
