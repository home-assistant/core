"""
A component which is collecting configuration errors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/persistent_notification/
"""
import os
import logging

import voluptuous as vol

from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.util import slugify
from homeassistant.config import load_yaml_config_file

DOMAIN = 'persistent_notification'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_CREATE = 'create'
ATTR_TITLE = 'title'
ATTR_MESSAGE = 'message'
ATTR_NOTIFICATION_ID = 'notification_id'

SCHEMA_SERVICE_CREATE = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE): cv.template,
    vol.Optional(ATTR_NOTIFICATION_ID): cv.string,
})


DEFAULT_OBJECT_ID = 'notification'
_LOGGER = logging.getLogger(__name__)


def create(hass, message, title=None, notification_id=None):
    """Generate a notification."""
    data = {
        key: value for key, value in [
            (ATTR_TITLE, title),
            (ATTR_MESSAGE, message),
            (ATTR_NOTIFICATION_ID, notification_id),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_CREATE, data)


def setup(hass, config):
    """Setup the persistent notification component."""
    def create_service(call):
        """Handle a create notification service call."""
        title = call.data.get(ATTR_TITLE)
        message = call.data.get(ATTR_MESSAGE)
        notification_id = call.data.get(ATTR_NOTIFICATION_ID)

        if notification_id is not None:
            entity_id = ENTITY_ID_FORMAT.format(slugify(notification_id))
        else:
            entity_id = generate_entity_id(ENTITY_ID_FORMAT, DEFAULT_OBJECT_ID,
                                           hass=hass)
        attr = {}
        if title is not None:
            try:
                title.hass = hass
                title = title.render()
            except TemplateError as ex:
                _LOGGER.error('Error rendering title %s: %s', title, ex)
                title = title.template

            attr[ATTR_TITLE] = title

        try:
            message.hass = hass
            message = message.render()
        except TemplateError as ex:
            _LOGGER.error('Error rendering message %s: %s', message, ex)
            message = message.template

        hass.states.set(entity_id, message, attr)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_CREATE, create_service,
                           descriptions[DOMAIN][SERVICE_CREATE],
                           SCHEMA_SERVICE_CREATE)

    return True
