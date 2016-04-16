"""
Provides functionality to launch a web browser on the host machine.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/browser/
"""
import voluptuous as vol

DOMAIN = "browser"
SERVICE_BROWSE_URL = "browse_url"

ATTR_URL = 'url'
ATTR_URL_DEFAULT = 'https://www.google.com'

SERVICE_BROWSE_URL_SCHEMA = vol.Schema({
    vol.Required(ATTR_URL, default=ATTR_URL_DEFAULT): vol.Url,
})


def setup(hass, config):
    """Listen for browse_url events."""
    import webbrowser

    hass.services.register(DOMAIN, SERVICE_BROWSE_URL,
                           lambda service:
                           webbrowser.open(service.data[ATTR_URL]),
                           schema=SERVICE_BROWSE_URL_SCHEMA)

    return True
