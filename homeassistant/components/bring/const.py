"""Constants for the Bring! integration."""

from typing import Final

DOMAIN = "bring"

ATTR_SENDER: Final = "sender"
ATTR_ITEM_NAME: Final = "item"
ATTR_NOTIFICATION_TYPE: Final = "message"
ATTR_REACTION: Final = "reaction"
ATTR_ACTIVITY: Final = "uuid"
ATTR_RECEIVER: Final = "publicUserUuid"
SERVICE_PUSH_NOTIFICATION = "send_message"
SERVICE_ACTIVITY_STREAM_REACTION = "send_reaction"
