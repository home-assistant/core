"""Constants for Music Assistant Component."""

import logging

DOMAIN = "music_assistant"
DOMAIN_EVENT = f"{DOMAIN}_event"

DEFAULT_NAME = "Music Assistant"

ATTR_IS_GROUP = "is_group"
ATTR_GROUP_MEMBERS = "group_members"
ATTR_GROUP_PARENTS = "group_parents"

ATTR_MASS_PLAYER_TYPE = "mass_player_type"
ATTR_ACTIVE_QUEUE = "active_queue"
ATTR_STREAM_TITLE = "stream_title"

LOGGER = logging.getLogger(__package__)
