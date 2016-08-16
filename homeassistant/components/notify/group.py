"""
Group platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.group/
"""
import logging
import voluptuous as vol

from homeassistant.const import (CONF_PLATFORM, CONF_NAME,
                                 CONF_ENTITY_ID)
from homeassistant.components.notify import (DOMAIN, ATTR_MESSAGE, ATTR_DATA,
                                             BaseNotificationService)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ENTITIES = "entities"

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "group",
    vol.Optional(CONF_NAME): vol.Coerce(str),
    vol.Required(CONF_ENTITIES): vol.All(cv.ensure_list, [{
        vol.Optional(CONF_ENTITY_ID): vol.Any(cv.string, None),
        vol.Optional(ATTR_DATA): dict,
    }])
})


def get_service(hass, config):
    """Get the Group notification service."""
    return GroupNotifyPlatform(hass, config.get(CONF_ENTITIES))


# pylint: disable=too-few-public-methods
class GroupNotifyPlatform(BaseNotificationService):
    """Implement the notification service for the group notify playform."""

    def __init__(self, hass, entities):
        """Initialize the service."""
        self.hass = hass
        self.entities = entities

    def send_message(self, message="", **kwargs):
        """Send message to all entities in the group."""
        cleaned_kwargs = dict((k, v) for k, v in kwargs.items() if v)
        payload = dict({ATTR_MESSAGE: message})
        payload.update(cleaned_kwargs)

        for entity in self.entities:
            sending_payload = payload.copy()
            if entity.get(ATTR_DATA) is not None:
                sending_payload.update(entity.get(ATTR_DATA))
            self.hass.services.call(DOMAIN, entity.get(CONF_ENTITY_ID),
                                    sending_payload)
