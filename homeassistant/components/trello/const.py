"""Constants for the trello integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "trello"

LOGGER = logging.getLogger(__package__)

CONF_USER_ID = "user_id"
CONF_USER_EMAIL = "user_email"
CONF_BOARD_IDS = "board_ids"
