"""Constants for Google Hangouts Component."""
import logging

import voluptuous as vol

from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TARGET
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger('homeassistant.components.hangouts')


DOMAIN = 'hangouts'

CONF_2FA = '2fa'
CONF_REFRESH_TOKEN = 'refresh_token'
CONF_BOT = 'bot'

CONF_CONVERSATIONS = 'conversations'
CONF_DEFAULT_CONVERSATIONS = 'default_conversations'

CONF_COMMANDS = 'commands'
CONF_WORD = 'word'
CONF_EXPRESSION = 'expression'

EVENT_HANGOUTS_COMMAND = 'hangouts_command'

EVENT_HANGOUTS_CONNECTED = 'hangouts_connected'
EVENT_HANGOUTS_DISCONNECTED = 'hangouts_disconnected'
EVENT_HANGOUTS_USERS_CHANGED = 'hangouts_users_changed'
EVENT_HANGOUTS_CONVERSATIONS_CHANGED = 'hangouts_conversations_changed'

CONF_CONVERSATION_ID = 'id'
CONF_CONVERSATION_NAME = 'name'

SERVICE_SEND_MESSAGE = 'send_message'
SERVICE_UPDATE = 'update'


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

MESSAGE_SCHEMA = vol.Schema({
    vol.Required(ATTR_TARGET): [TARGETS_SCHEMA],
    vol.Required(ATTR_MESSAGE): [MESSAGE_SEGMENT_SCHEMA]
})

COMMAND_SCHEMA = vol.All(
    # Basic Schema
    vol.Schema({
        vol.Exclusive(CONF_WORD, 'trigger'): cv.string,
        vol.Exclusive(CONF_EXPRESSION, 'trigger'): cv.is_regex,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_CONVERSATIONS): [TARGETS_SCHEMA]
    }),
    # Make sure it's either a word or an expression command
    cv.has_at_least_one_key(CONF_WORD, CONF_EXPRESSION)
)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_COMMANDS, default=[]): [COMMAND_SCHEMA]
    })
}, extra=vol.ALLOW_EXTRA)
