"""Constants for the klyqa integration."""

import logging

LOGGER = logging.getLogger(__package__)
formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s - %(name)s - %(levelname)s - %(message)s"
)

ch = logging.StreamHandler()
ch.setLevel(level=logging.DEBUG)
ch.setFormatter(formatter)

LOGGER.addHandler(ch)

DOMAIN = "klyqa"


CONF_POLLING = "polling"
CONF_SYNC_ROOMS = "sync_rooms"
EVENT_KLYQA_NEW_LIGHT = "klyqa_new_light"
EVENT_KLYQA_NEW_LIGHT_GROUP = "klyqa_new_light_group"
REQUEST_TIMEOUT = 11000
