"""
A component which is collecting configuration errors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/persistent_notification/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.loader import bind_hass
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

ATTR_MESSAGE = 'message'
ATTR_NOTIFICATION_ID = 'notification_id'
ATTR_TITLE = 'title'

DOMAIN = 'persistent_notification'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_CREATE = 'create'
SERVICE_DISMISS = 'dismiss'

SCHEMA_SERVICE_CREATE = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE): cv.template,
    vol.Optional(ATTR_NOTIFICATION_ID): cv.string,
})

SCHEMA_SERVICE_DISMISS = vol.Schema({
    vol.Required(ATTR_NOTIFICATION_ID): cv.string,
})


DEFAULT_OBJECT_ID = 'notification'
_LOGGER = logging.getLogger(__name__)

STATE = 'notifying'


@bind_hass
def create(hass, message, title=None, notification_id=None):
    """Generate a notification."""
    hass.add_job(async_create, hass, message, title, notification_id)


@bind_hass
def dismiss(hass, notification_id):
    """Remove a notification."""
    hass.add_job(async_dismiss, hass, notification_id)


@callback
@bind_hass
def async_create(hass, message, title=None, notification_id=None):
    """Generate a notification."""
    data = {
        key: value for key, value in [
            (ATTR_TITLE, title),
            (ATTR_MESSAGE, message),
            (ATTR_NOTIFICATION_ID, notification_id),
        ] if value is not None
    }

    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_CREATE, data))


@callback
@bind_hass
def async_dismiss(hass, notification_id):
    """Remove a notification."""
    data = {ATTR_NOTIFICATION_ID: notification_id}

    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_DISMISS, data))


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the persistent notification component."""
    @callback
    def create_service(call):
        """Handle a create notification service call."""
        title = call.data.get(ATTR_TITLE)
        message = call.data.get(ATTR_MESSAGE)
        notification_id = call.data.get(ATTR_NOTIFICATION_ID)

        if notification_id is not None:
            entity_id = ENTITY_ID_FORMAT.format(slugify(notification_id))
        else:
            entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, DEFAULT_OBJECT_ID, hass=hass)
        attr = {}
        if title is not None:
            try:
                title.hass = hass
                title = title.async_render()
            except TemplateError as ex:
                _LOGGER.error('Error rendering title %s: %s', title, ex)
                title = title.template

            attr[ATTR_TITLE] = title

        try:
            message.hass = hass
            message = message.async_render()
        except TemplateError as ex:
            _LOGGER.error('Error rendering message %s: %s', message, ex)
            message = message.template

        attr[ATTR_MESSAGE] = message

        hass.states.async_set(entity_id, STATE, attr)

    @callback
    def dismiss_service(call):
        """Handle the dismiss notification service call."""
        notification_id = call.data.get(ATTR_NOTIFICATION_ID)
        entity_id = ENTITY_ID_FORMAT.format(slugify(notification_id))

        hass.states.async_remove(entity_id)

    hass.services.async_register(DOMAIN, SERVICE_CREATE, create_service,
                                 SCHEMA_SERVICE_CREATE)

    hass.services.async_register(DOMAIN, SERVICE_DISMISS, dismiss_service,
                                 SCHEMA_SERVICE_DISMISS)

    return True
