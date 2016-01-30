"""
custom_components.hello_world
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Implements the bare minimum that a component should implement.
Configuration:
To use the hello_word component you will need to add the following to your
configuration.yaml file.
hello_world:
"""

# The domain of your component. Should be equal to the name of your component
import logging
from datetime import timedelta

import requests

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = "server"

ATTR_ENTITY = 'entity'
ATTR_URL = 'url'
ATTR_ICON = 'icon'
WEBLINK_ICON = 'mdi:open-in-new'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

# List of component names (string) your component depends upon
DEPENDENCIES = []


def setup(hass, config):
    """ Setup our skeleton component. """
    links = config.get(DOMAIN)

    for link in links:
        Link(hass, link.get(ATTR_ENTITY), link.get(ATTR_URL), WEBLINK_ICON)

    # return boolean to indicate that initialization was successful
    return True


class Link(Entity):

    def __init__(self, hass, name, url, icon=None):
        super(Link, self).__init__()
        self._name = name
        self.hass = hass
        self._icon = icon
        self._url = url
        self.service = UrlData('GET')
        self.entity_id = ".".join([DOMAIN, name])
        self.update_ha_state()

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    def state(self):
        return 'up' if self.service.update() == 200 else 'down'


# pylint: disable=too-few-public-methods
class UrlData(object):
    """Class for handling the data retrieval."""

    def __init__(self, method, url):
        self.url = url
        self.data = None
        self._request = requests.Request(method, self.url).prepare()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from REST service with GET method. """
        try:
            with requests.Session() as sess:
                response = sess.send(self._request, timeout=10)

            self.data = response.status
        except requests.exceptions.RequestException:
            _LOGGER.error("Error fetching data: %s", self._request)
            self.data = None
