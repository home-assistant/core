"""Constants for the smtp integration."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "smtp"

ATTR_IMAGES: Final = "images"  # optional embedded image file attachments
ATTR_HTML: Final = "html"
CONF_ENCRYPTION: Final = "encryption"
CONF_SERVER: Final = "server"
CONF_SENDER_NAME: Final = "sender_name"
SECTION_OPTIONS: Final = "options"

DEFAULT_HOST: Final = "localhost"
DEFAULT_PORT: Final = 587
DEFAULT_TIMEOUT: Final = 60
DEFAULT_DEBUG: Final = False
DEFAULT_ENCRYPTION: Final = "starttls"

ENCRYPTION_OPTIONS: Final = ["tls", "starttls", "none"]

SUBENTRY_TYPE_RECIPIENT: Final = "recipient"
CONF_ENTRY = "entry"
CONF_OLD_RECIPIENT: Final = "old_recipient"

CONF_REPLY_TO: Final = "reply_to"
CONF_REPLY_TO_NAME: Final = "reply_to_name"


class SMTPService(StrEnum):
    """Store keys for SMTP services."""

    SEND_MESSAGE = "send_message"


class SMTPServiceArgument(StrEnum):
    """Store keys for SMTP service arguments."""

    TITLE = "title"
    MESSAGE = "message"
    HTML = "html"
    ATTACHMENTS = "attachments"
    PRIORITY = "priority"


class SMTPServiceAttachment(StrEnum):
    """Store keys for SMTP service attachments argument."""

    MEDIA_SOURCE = "media_source"
    FILENAME = "filename"
    CONTENT_ID = "content_id"
