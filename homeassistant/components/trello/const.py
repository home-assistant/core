"""Constants for the trello_int integration."""
import logging
from typing import Final

DOMAIN: Final = "trello"

LOGGER = logging.getLogger(__package__)

CONF_API_TOKEN = "api_token"
CONF_USER_ID = "user_id"
CONF_USER_EMAIL = "user_email"

CONF_OPTIONS_BOARDS = "boards"

USER_INPUT_BOARD_IDS = "board_ids"
