"""Constants for the Matrix integration."""

from enum import StrEnum

DOMAIN = "matrix"


class MatrixService(StrEnum):
    """Store keys for Matrix services."""

    SEND_MESSAGE = "send_message"
    REACT = "react"


class MatrixServiceArgument(StrEnum):
    """Store keys for Matrix service arguments."""

    MESSAGE = "message"
    TARGET = "target"
    DATA = "data"
    REACTION = "reaction"
    ROOM = "room"
    MESSAGE_ID = "message_id"


FORMAT_HTML = "html"
FORMAT_TEXT = "text"

ATTR_FORMAT = "format"  # optional message format
ATTR_IMAGES = "images"  # optional images
ATTR_THREAD_ID = "thread_id"  # optional thread id

# Room IDs from room version 12 on no longer include the server name
CONF_ROOMS_REGEX = "^(![^:]+(:.+)?|#[^:]+:.+)$"
