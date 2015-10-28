"""
homeassistant.components.browser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to launch a webbrowser on the host machine.
"""

import logging
from homeassistant.helpers import set_log_severity

DOMAIN = "browser"
DEPENDENCIES = []

SERVICE_BROWSE_URL = "browse_url"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Listen for browse_url events and open
        the url in the default webbrowser. """

    import webbrowser

    set_log_severity(hass, config, _LOGGER)

    hass.services.register(DOMAIN, SERVICE_BROWSE_URL,
                           lambda service:
                           webbrowser.open(
                               service.data.get(
                                   'url', 'https://www.google.com')))

    return True
