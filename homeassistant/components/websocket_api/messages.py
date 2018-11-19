"""Message templates for websocket commands."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from . import const


# Minimal requirements of a message
MINIMAL_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): cv.string,
}, extra=vol.ALLOW_EXTRA)

# Base schema to extend by message handlers
BASE_COMMAND_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
})


def result_message(iden, result=None):
    """Return a success result message."""
    return {
        'id': iden,
        'type': const.TYPE_RESULT,
        'success': True,
        'result': result,
    }


def error_message(iden, code, message):
    """Return an error result message."""
    return {
        'id': iden,
        'type': const.TYPE_RESULT,
        'success': False,
        'error': {
            'code': code,
            'message': message,
        },
    }
