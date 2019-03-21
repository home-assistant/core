"""Constants for Google Hangouts Component."""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger('.')


DOMAIN = 'hangouts'

CONF_2FA = '2fa'
CONF_REFRESH_TOKEN = 'refresh_token'
CONF_BOT = 'bot'

CONF_CONVERSATIONS = 'conversations'
CONF_DEFAULT_CONVERSATIONS = 'default_conversations'
CONF_ERROR_SUPPRESSED_CONVERSATIONS = 'error_suppressed_conversations'

CONF_INTENTS = 'intents'
CONF_INTENT_TYPE = 'intent_type'
CONF_SENTENCES = 'sentences'
CONF_MATCHERS = 'matchers'

INTENT_HELP = 'HangoutsHelp'

EVENT_HANGOUTS_CONNECTED = 'hangouts_connected'
EVENT_HANGOUTS_DISCONNECTED = 'hangouts_disconnected'
EVENT_HANGOUTS_USERS_CHANGED = 'hangouts_users_changed'
EVENT_HANGOUTS_CONVERSATIONS_CHANGED = 'hangouts_conversations_changed'
EVENT_HANGOUTS_CONVERSATIONS_RESOLVED = 'hangouts_conversations_resolved'
EVENT_HANGOUTS_MESSAGE_RECEIVED = 'hangouts_message_received'

CONF_CONVERSATION_ID = 'id'
CONF_CONVERSATION_NAME = 'name'

SERVICE_SEND_MESSAGE = 'send_message'
SERVICE_UPDATE = 'update'
SERVICE_RECONNECT = 'reconnect'


TARGETS_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_CONVERSATION_ID, 'id or name'): cv.string,
        vol.Exclusive(CONF_CONVERSATION_NAME, 'id or name'): cv.string
    }),
    cv.has_at_least_one_key(CONF_CONVERSATION_ID, CONF_CONVERSATION_NAME)
)
MESSAGE_SEGMENT_SCHEMA = vol.Schema({
    vol.Required('text'): cv.string,
    vol.Optional('is_bold'): cv.boolean,
    vol.Optional('is_italic'): cv.boolean,
    vol.Optional('is_strikethrough'): cv.boolean,
    vol.Optional('is_underline'): cv.boolean,
    vol.Optional('parse_str'): cv.boolean,
    vol.Optional('link_target'): cv.string
})
MESSAGE_DATA_SCHEMA = vol.Schema({
    vol.Optional('image_file'): cv.string,
    vol.Optional('image_url'): cv.string
})

MESSAGE_SCHEMA = vol.Schema({
    vol.Required(ATTR_TARGET): [TARGETS_SCHEMA],
    vol.Required(ATTR_MESSAGE): [MESSAGE_SEGMENT_SCHEMA],
    vol.Optional(ATTR_DATA): MESSAGE_DATA_SCHEMA
})

INTENT_SCHEMA = vol.All(
    # Basic Schema
    vol.Schema({
        vol.Required(CONF_SENTENCES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_CONVERSATIONS): [TARGETS_SCHEMA]
    }),
)
