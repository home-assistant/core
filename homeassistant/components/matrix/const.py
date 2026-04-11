"""Constants for the Matrix integration."""

from typing import Final

DOMAIN: Final = "matrix"

CONF_ROOMS: Final = "rooms"
CONF_COMMANDS: Final = "commands"
CONF_WORD: Final = "word"
CONF_EXPRESSION: Final = "expression"
CONF_REACTION: Final = "reaction"

SERVICE_SEND_MESSAGE: Final = "send_message"
SERVICE_REACT: Final = "react"

FORMAT_HTML: Final = "html"
FORMAT_TEXT: Final = "text"

ATTR_FORMAT: Final = "format"  # optional message format
ATTR_IMAGES: Final = "images"  # optional images
ATTR_THREAD_ID: Final = "thread_id"  # optional thread id

ATTR_REACTION: Final = "reaction"  # reaction
ATTR_ROOM: Final = "room"  # room id
ATTR_MESSAGE_ID: Final = "message_id"  # message id

CONF_CONFIG_ENTRY_ID: Final = "config_entry_id"

CONF_HOMESERVER: Final = "homeserver"
CONF_ROOMS_REGEX: Final = "^[!#][^:]*:.*"

DEFAULT_HOMESERVER: Final = "https://matrix.org"
