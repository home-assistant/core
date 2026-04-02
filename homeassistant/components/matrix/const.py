"""Constants for the Matrix integration."""

DOMAIN = "matrix"

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_REACT = "react"

FORMAT_HTML = "html"
FORMAT_TEXT = "text"

ATTR_FORMAT = "format"  # optional message format
ATTR_IMAGES = "images"  # optional images
ATTR_THREAD_ID = "thread_id"  # optional thread id

ATTR_REACTION = "reaction"  # reaction
ATTR_ROOM = "room"  # room id
ATTR_MESSAGE_ID = "message_id"  # message id

CONF_ROOMS_REGEX = "^[!|#][^:]*:.*"
