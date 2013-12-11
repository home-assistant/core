"""
homeassistant.components.browser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to launch a webbrowser on the host machine.
"""

DOMAIN_BROWSER = "browser"

SERVICE_BROWSE_URL = "browse_url"


def setup(bus):
    """ Listen for browse_url events and open
        the url in the default webbrowser. """

    import webbrowser

    bus.register_service(DOMAIN_BROWSER, SERVICE_BROWSE_URL,
                         lambda service: webbrowser.open(service.data['url']))

    return True
