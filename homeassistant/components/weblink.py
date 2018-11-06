"""
Support for links to external web pages.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/weblink/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_ICON, CONF_URL,
                                 CONF_VALUE_TEMPLATE)
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ENTITIES = 'entities'
CONF_RELATIVE_URL_ERROR_MSG = "Invalid relative URL. Absolute path required."
CONF_RELATIVE_URL_REGEX = r'\A/'

DOMAIN = 'weblink'

ENTITIES_SCHEMA = vol.Schema({
    # pylint: disable=no-value-for-parameter
    vol.Optional(CONF_URL): vol.Any(
        vol.Match(CONF_RELATIVE_URL_REGEX, msg=CONF_RELATIVE_URL_ERROR_MSG),
        vol.Url()),
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ENTITIES): [ENTITIES_SCHEMA],
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the weblink component."""
    links = config.get(DOMAIN)

    for link in links.get(CONF_ENTITIES):
        value_template = link.get(CONF_VALUE_TEMPLATE)
        if value_template:
            value_template.hass = hass
            url = value_template.render()
        else:
            url = link.get(CONF_URL)

        Link(hass, link.get(CONF_NAME), url,
             link.get(CONF_ICON))

    return True


class Link(Entity):
    """Representation of a link."""

    def __init__(self, hass, name, url, icon):
        """Initialize the link."""
        self.hass = hass
        self._name = name
        self._url = url
        self._icon = icon
        self.entity_id = DOMAIN + '.%s' % slugify(name)
        self.schedule_update_ha_state()

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def name(self):
        """Return the name of the URL."""
        return self._name

    @property
    def state(self):
        """Return the URL."""
        return self._url
