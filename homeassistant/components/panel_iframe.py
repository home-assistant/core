"""
Register an iFrame front end panel.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/panel_iframe/
"""
import asyncio

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = 'panel_iframe'
DEPENDENCIES = ['frontend']

CONF_TITLE = 'title'
CONF_ICON = 'icon'
CONF_URL = 'url'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: {
            vol.Optional(CONF_TITLE): cv.string,
            vol.Optional(CONF_ICON): cv.icon,
            # pylint: disable=no-value-for-parameter
            vol.Required(CONF_URL): vol.Url(),
        }})}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def setup(hass, config):
    """Set up the iFrame frontend panels."""
    for url_path, info in config[DOMAIN].items():
        yield from hass.components.frontend.async_register_built_in_panel(
            'iframe', info.get(CONF_TITLE), info.get(CONF_ICON),
            url_path, {'url': info[CONF_URL]})

    return True
