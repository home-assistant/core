"""Constants for the imap integration."""

from typing import Final
import logging
DOMAIN: Final = "imap"

CONF_SERVER: Final = "server"
CONF_FOLDER: Final = "folder"
CONF_SEARCH: Final = "search"
CONF_CHARSET: Final = "charset"
CONF_MESSAGE_DATA = "message_data"
CONF_MAX_MESSAGE_SIZE = "max_message_size"
CONF_CUSTOM_EVENT_DATA_TEMPLATE: Final = "custom_event_data_template"
CONF_SSL_CIPHER_LIST: Final = "ssl_cipher_list"
CONF_ENABLE_PUSH: Final = "enable_push"

DEFAULT_PORT: Final = 993

DEFAULT_MAX_MESSAGE_SIZE = 2048

DEFAULT_MESSAGE_DATA = ["date", "text", "sender", "subject", "headers"]

MAX_MESSAGE_SIZE_LIMIT = 30000

LOGGER = logging.getLogger(__package__)
