"""Constants for Google Mail integration."""

from typing import Any

from homeassistant.util.hass_dict import HassKey

ATTR_BCC = "bcc"
ATTR_CC = "cc"
ATTR_ENABLED = "enabled"
ATTR_END = "end"
ATTR_FROM = "from"
ATTR_ALIAS_FROM = "alias_from"
ATTR_ME = "me"
ATTR_MESSAGE = "message"
ATTR_PLAIN_TEXT = "plain_text"
ATTR_RESTRICT_CONTACTS = "restrict_contacts"
ATTR_RESTRICT_DOMAIN = "restrict_domain"
ATTR_SEND = "send"
ATTR_START = "start"
ATTR_TITLE = "title"

DATA_AUTH = "auth"
# Domain-level root HA config for legacy notify platform discovery.
# Not per config entry — entries store auth on entry.runtime_data.
DATA_HASS_CONFIG: HassKey[dict[str, Any]] = HassKey("google_mail_hass_config")
DEFAULT_ACCESS = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]
DOMAIN = "google_mail"
MANUFACTURER = "Google, Inc."
