"""Type definitions and schemas for the Matrix component."""

from __future__ import annotations

import re
from typing import Final, NewType, Required, TypedDict

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

from .const import CONF_ROOMS_REGEX, DOMAIN

# Configuration constants
CONF_HOMESERVER: Final = "homeserver"
CONF_ROOMS: Final = "rooms"
CONF_COMMANDS: Final = "commands"
CONF_WORD: Final = "word"
CONF_EXPRESSION: Final = "expression"

CONF_USERNAME_REGEX = "^@[^:]*:.*"

# Type definitions
WordCommand = NewType("WordCommand", str)
ExpressionCommand = NewType("ExpressionCommand", re.Pattern)
RoomAlias = NewType("RoomAlias", str)  # Starts with "#"
RoomID = NewType("RoomID", str)  # Starts with "!"
RoomAnyID = RoomID | RoomAlias


class ConfigCommand(TypedDict, total=False):
    """Corresponds to a single COMMAND_SCHEMA."""

    name: Required[str]  # CONF_NAME
    rooms: list[RoomID]  # CONF_ROOMS
    word: WordCommand  # CONF_WORD
    expression: ExpressionCommand  # CONF_EXPRESSION


# Schema definitions
COMMAND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_WORD, "trigger"): cv.string,
            vol.Exclusive(CONF_EXPRESSION, "trigger"): cv.is_regex,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_ROOMS): vol.All(
                cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_WORD, CONF_EXPRESSION),
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("homeserver"): cv.url,
                vol.Optional("verify_ssl", default=True): cv.boolean,
                vol.Required("username"): cv.matches_regex(CONF_USERNAME_REGEX),
                vol.Required("password"): cv.string,
                vol.Optional("device_id", default="Home Assistant"): cv.string,
                vol.Optional("rooms", default=[]): vol.All(
                    cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
                ),
                vol.Optional("commands", default=[]): [COMMAND_SCHEMA],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
