"""
Register a custom front end panel.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/panel_custom/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = 'panel_custom'
DEPENDENCIES = ['frontend']

CONF_COMPONENT_NAME = 'name'
CONF_SIDEBAR_TITLE = 'sidebar_title'
CONF_SIDEBAR_ICON = 'sidebar_icon'
CONF_URL_PATH = 'url_path'
CONF_CONFIG = 'config'
CONF_WEBCOMPONENT_PATH = 'webcomponent_path'
CONF_JS_URL = 'js_url'
CONF_EMBED_IFRAME = 'embed_iframe'
CONF_TRUST_EXTERNAL_SCRIPT = 'trust_external_script'

DEFAULT_ICON = 'mdi:bookmark'
LEGACY_URL = '/api/panel_custom/{}'

PANEL_DIR = 'panels'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_COMPONENT_NAME): cv.string,
        vol.Optional(CONF_SIDEBAR_TITLE): cv.string,
        vol.Optional(CONF_SIDEBAR_ICON, default=DEFAULT_ICON): cv.icon,
        vol.Optional(CONF_URL_PATH): cv.string,
        vol.Optional(CONF_CONFIG): dict,
        vol.Optional(CONF_WEBCOMPONENT_PATH): cv.isfile,
        vol.Optional(CONF_JS_URL): cv.string,
        vol.Optional(CONF_EMBED_IFRAME, default=False): cv.boolean,
        vol.Optional(CONF_TRUST_EXTERNAL_SCRIPT, default=False): cv.boolean,
    })])
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Initialize custom panel."""
    success = False

    for panel in config.get(DOMAIN):
        name = panel.get(CONF_COMPONENT_NAME)
        panel_path = panel.get(CONF_WEBCOMPONENT_PATH)

        if panel_path is None:
            panel_path = hass.config.path(PANEL_DIR, '{}.html'.format(name))

        custom_panel_config = {
            'name': name,
            'embed_iframe': panel[CONF_EMBED_IFRAME],
            'trust_external': panel[CONF_TRUST_EXTERNAL_SCRIPT],
        }

        if CONF_JS_URL in panel:
            custom_panel_config['js_url'] = panel[CONF_JS_URL]

        elif not await hass.async_add_job(os.path.isfile, panel_path):
            _LOGGER.error('Unable to find webcomponent for %s: %s',
                          name, panel_path)
            continue

        else:
            url = LEGACY_URL.format(name)
            hass.http.register_static_path(url, panel_path)
            custom_panel_config['html_url'] = LEGACY_URL.format(name)

        if CONF_CONFIG in panel:
            # Make copy because we're mutating it
            config = dict(panel[CONF_CONFIG])
        else:
            config = {}

        config['_panel_custom'] = custom_panel_config

        await hass.components.frontend.async_register_built_in_panel(
            component_name='custom',
            sidebar_title=panel.get(CONF_SIDEBAR_TITLE),
            sidebar_icon=panel.get(CONF_SIDEBAR_ICON),
            frontend_url_path=panel.get(CONF_URL_PATH),
            config=config
        )

        success = True

    return success
