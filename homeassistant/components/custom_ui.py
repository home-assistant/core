"""
Register a custom polymer ui block.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/custom_ui/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.frontend import register_custom_ui

DOMAIN = 'custom_ui'
DEPENDENCIES = ['frontend']

CONF_COMPONENT_NAME = 'name'
CONF_URL_PATH = 'url_path'
CONF_CONFIG = 'config'
CONF_WEBCOMPONENT_PATH = 'webcomponent_path'

CUSTOM_UI_DIR = 'custom_ui'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [{
        vol.Required(CONF_COMPONENT_NAME): cv.string,
        vol.Optional(CONF_URL_PATH): cv.string,
        vol.Optional(CONF_CONFIG): cv.match_all,
        vol.Optional(CONF_WEBCOMPONENT_PATH): cv.isfile,
    }])
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Initialize custom ui."""
    success = False

    for custom_ui_config in config.get(DOMAIN):
        name = custom_ui_config.get(CONF_COMPONENT_NAME)
        path = custom_ui_config.get(CONF_WEBCOMPONENT_PATH)

        if path is None:
            path = hass.config.path(CUSTOM_UI_DIR, '{}.html'.format(name))

        if not os.path.isfile(path):
            _LOGGER.error('Unable to find custom ui component for %s at: %s',
                          name, path)
            continue

        register_custom_ui(
            hass, name, path,
            url_path=custom_ui_config.get(CONF_URL_PATH),
            config=custom_ui_config.get(CONF_CONFIG),
        )

        success = True

    return success
