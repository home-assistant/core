"""Constants for Google Mail integration."""

from __future__ import annotations

ATTR_BCC = "bcc"
ATTR_CC = "cc"
ATTR_ENABLED = "enabled"
ATTR_END = "end"
ATTR_FILES = "files"
ATTR_FILE_CONTENT = "content"
ATTR_FILE_KIND_FILE = "file"
ATTR_FILE_KIND_IMAGE = "image"
ATTR_FILE_MIME_TYPE = "mime_type"
ATTR_FILE_NAME = "name"
ATTR_FILE_PATH = "path"
ATTR_FILE_URL = "url"
ATTR_FROM = "from"
ATTR_HTML = "html"
ATTR_IMAGES = "images"
ATTR_LEVEL = "level"
ATTR_ME = "me"
ATTR_MESSAGE = "message"
ATTR_PLAIN_TEXT = "plain_text"
ATTR_PRIORITY = "priority"
ATTR_RESTRICT_CONTACTS = "restrict_contacts"
ATTR_RESTRICT_DOMAIN = "restrict_domain"
ATTR_SEND = "send"
ATTR_START = "start"
ATTR_TITLE = "title"

DATA_AUTH = "auth"
DATA_HASS_CONFIG = "hass_config"
DEFAULT_ACCESS = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]
DOMAIN = "google_mail"
MANUFACTURER = "Google, Inc."
