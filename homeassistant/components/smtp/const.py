"""Constants for the smtp integration."""

from typing import Final

DOMAIN: Final = "smtp"

ATTR_IMAGES: Final = "images"  # optional embedded image file attachments
ATTR_HTML: Final = "html"
ATTR_SENDER_NAME: Final = "sender_name"

CONF_ENCRYPTION: Final = "encryption"
CONF_DEBUG: Final = "debug"
CONF_SERVER: Final = "server"
CONF_SENDER_NAME: Final = "sender_name"

DEFAULT_HOST: Final = "localhost"
DEFAULT_PORT: Final = 587
DEFAULT_TIMEOUT: Final = 5
DEFAULT_DEBUG: Final = False
DEFAULT_ENCRYPTION: Final = "starttls"

ENCRYPTION_OPTIONS: Final = ["tls", "starttls", "none"]
