"""
Hangouts notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.hangouts/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (ATTR_TARGET, PLATFORM_SCHEMA, NOTIFY_SERVICE_SCHEMA,
                                             BaseNotificationService,
                                             ATTR_MESSAGE)

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_CONVERSATIONS = 'default_conversations'
CONF_CONVERSATION_ID = 'id'
CONF_CONVERSATION_NAME = 'name'

DOMAIN = 'hangouts'
DEPENDENCIES = [DOMAIN]

TARGETS_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_CONVERSATION_ID, 'id'): cv.string,
        vol.Exclusive(CONF_CONVERSATION_NAME, 'id'): cv.string
    }),
    cv.has_at_least_one_key(CONF_CONVERSATION_ID, CONF_CONVERSATION_NAME)
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEFAULT_CONVERSATIONS): [TARGETS_SCHEMA]
})

NOTIFY_SERVICE_SCHEMA = NOTIFY_SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_TARGET): [TARGETS_SCHEMA]
})


def get_service(hass, config, discovery_info=None):
    """Get the Hangouts notification service."""
    return HangoutsNotificationService(config.get(CONF_DEFAULT_CONVERSATIONS))


class HangoutsNotificationService(BaseNotificationService):
    """Send Notifications to Hangouts conversations."""

    def __init__(self, default_conversations):
        """Set up the notification service."""
        self._default_conversations = default_conversations

    def send_message(self, message="", **kwargs):
        """Send the message to the Google Hangouts server."""
        target_conversations = None
        if ATTR_TARGET in kwargs:
            target_conversations = []
            for target in kwargs.get(ATTR_TARGET):
                target_conversations.append({'id':target})
        else:
            target_conversations = self._default_conversations

        service_data = {
            ATTR_TARGET: target_conversations,
            ATTR_MESSAGE: [{'text': message, 'parse_str': True}]
        }

        return self.hass.services.call(
            DOMAIN, 'send_message', service_data=service_data)
