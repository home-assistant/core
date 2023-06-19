"""Constants for the trello integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

DOMAIN: Final = "trello"

LOGGER = logging.getLogger(__package__)

CONF_API_TOKEN = "api_token"
CONF_USER_ID = "user_id"
CONF_USER_EMAIL = "user_email"
CONF_BOARD_IDS = "board_ids"


@dataclass
class Board:
    """A Trello board."""

    id: str
    name: str
    lists: dict[str, List]


@dataclass
class List:
    """A Trello list."""

    id: str
    name: str
    card_count: int
