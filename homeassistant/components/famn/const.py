"""Constants for the Famn integration."""

import logging
from typing import Final

DOMAIN: Final = "famn"

LOGGER = logging.getLogger(__package__)

BASE_URL: Final = "https://famn.app"

CONF_REFRESH_TOKEN: Final = "refresh_token"

# Task types of the lists exposed as todo entities. Chore lists recur and
# only support marking items done; todo lists are one-off and also support
# creating items from Home Assistant.
TASK_TYPE_CHORES: Final = "chores"
TASK_TYPE_TODOS: Final = "todos"

# Fired on the Home Assistant event bus for every realtime event the Famn
# gateway pushes for the paired space, so users can build automations on
# family activity ("chore completed -> flash the kid's light").
EVENT_FAMN_EVENT: Final = "famn_event"
