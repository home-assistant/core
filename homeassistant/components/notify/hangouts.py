"""
Hangouts notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.hangouts/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (ATTR_TARGET, PLATFORM_SCHEMA,
                                             NOTIFY_SERVICE_SCHEMA,
                                             BaseNotificationService,
                                             ATTR_MESSAGE)

from homeassistant.components.hangouts.const \
    import (DOMAIN, SERVICE_SEND_MESSAGE,
            TARGETS_SCHEMA, CONF_DEFAULT_CONVERSATIONS)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [DOMAIN]

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
                target_conversations.append({'id': target})
        else:
            target_conversations = self._default_conversations

        messages = []
        if 'title' in kwargs:
            messages.append({'text': kwargs['title'], 'is_bold': True})

        messages.append({'text': message, 'parse_str': True})
        service_data = {
            ATTR_TARGET: target_conversations,
            ATTR_MESSAGE: messages
        }

        return self.hass.services.call(
            DOMAIN, SERVICE_SEND_MESSAGE, service_data=service_data)
