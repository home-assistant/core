"""
Support for links to external web pages.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/weblink/
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

DOMAIN = "weblink"
DEPENDENCIES = []

ATTR_NAME = 'name'
ATTR_URL = 'url'
ATTR_ICON = 'icon'

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup weblink component."""
    links = config.get(DOMAIN)

    for link in links.get('entities'):
        if ATTR_NAME not in link or ATTR_URL not in link:
            _LOGGER.error("You need to set both %s and %s to add a %s",
                          ATTR_NAME, ATTR_URL, DOMAIN)
            continue
        Link(hass, link.get(ATTR_NAME), link.get(ATTR_URL),
             link.get(ATTR_ICON))

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
        self.update_ha_state()

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
