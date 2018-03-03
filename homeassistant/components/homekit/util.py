"""Collection of useful functions for the HomeKit component."""
import logging
import os

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.const import (
    ATTR_CODE)
import homeassistant.helpers.config_validation as cv
from .const import (
    CONF_AID, CONF_AUTO_START, CONF_EVENTS, HOMEKIT_NOTIFY_ID, QR_CODE_NAME)

_LOGGER = logging.getLogger(__name__)


def validate_aid(entity, value, aids):
    """Validate the value is a unique aid."""
    if value < 2:
        raise vol.Invalid('Accessory ID for "{}" must be 2 or higher'
                          .format(entity))
    if value in aids:
        raise vol.Invalid('Accessory ID for "{}" is not unique'
                          .format(entity))
    aids.add(value)
    return value


def validate_entities(values):
    """Validate config entry for 'entities'."""
    aids = set()
    entities = {}
    for key, config in values.items():
        entity = cv.entity_id(key)
        params = {}
        if isinstance(config, int):
            params[CONF_AID] = validate_aid(entity, config, aids)
        elif isinstance(config, dict):
            aid = config.get(CONF_AID, None)
            if isinstance(aid, int):
                params[CONF_AID] = validate_aid(entity, aid, aids)
            else:
                raise vol.Invalid('"{}" must have an unique Accessory ID'
                                  .format(entity))
            config.pop(CONF_AID, None)
            domain, _ = split_entity_id(entity)
            # Domain specific config options can be added here
            if domain == 'alarm_control_panel':
                code = config.get(ATTR_CODE)
                params[ATTR_CODE] = cv.string(code) if code else None
        else:
            raise vol.Invalid(
                'The configuration for "{}" must either be '
                'of type integer or type dictionary.'.format(entity))
        entities[entity] = params
    return entities


def validate_events_auto_start(config):
    """Validate that if events are given auto_start must be true."""
    if config[CONF_EVENTS] and not config[CONF_AUTO_START]:
        raise vol.Invalid('"auto_start" must be "True" for for "events" to'
                          ' have an effect.')
    return config


def show_setup_message(bridge, hass):
    """Display persistent notification with setup information."""
    pin = bridge.pincode.decode()
    path = hass.config.path('www/' + QR_CODE_NAME)
    try:
        bridge.qr_code.png(path, scale=12, quiet_zone=2,
                           background=(239, 239, 239))
    except OSError:
        _LOGGER.warning('Could not generate a PNG QR Code in "%s"', path)
    if os.path.isfile(path):
        message = 'To setup Home Assistant in the Home App, enter the ' \
                  'following code:\n### {}\nor scan the QR code below.\n### ' \
                  '\n![HomeKit QR Code](/local/{})' \
                  .format(pin, QR_CODE_NAME)
    else:
        message = 'To setup Home Assistant in the Home App, enter the ' \
                  'following code:\n### {}'.format(pin)
    hass.components.persistent_notification.create(
        message, 'HomeKit Setup', HOMEKIT_NOTIFY_ID)


def dismiss_setup_message(hass):
    """Dismiss persistent notification and remove QR code."""
    hass.components.persistent_notification.dismiss(HOMEKIT_NOTIFY_ID)

    path = hass.config.path('www/' + QR_CODE_NAME)
    try:
        os.remove(path)
    except OSError:
        pass
