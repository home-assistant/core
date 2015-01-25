"""
homeassistant.components.browser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to launch a webbrowser on the host machine.
"""

DOMAIN = "browser"
DEPENDENCIES = []

SERVICE_BROWSE_URL = "browse_url"


def setup(hass, config):
    """ Listen for browse_url events and open
        the url in the default webbrowser. """

    import webbrowser

    hass.services.register(DOMAIN, SERVICE_BROWSE_URL,
                           lambda service:
                           webbrowser.open(
                               service.data.get(
                                   'url', 'https://www.google.com')))

    return True
