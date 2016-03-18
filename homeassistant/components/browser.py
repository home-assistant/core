"""
Provides functionality to launch a web browser on the host machine.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/browser/
"""

DOMAIN = "browser"
SERVICE_BROWSE_URL = "browse_url"


def setup(hass, config):
    """Listen for browse_url events."""
    import webbrowser

    hass.services.register(DOMAIN, SERVICE_BROWSE_URL,
                           lambda service:
                           webbrowser.open(
                               service.data.get(
                                   'url', 'https://www.google.com')))

    return True
