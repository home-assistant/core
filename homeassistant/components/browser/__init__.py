"""Support for launching a web browser on the host machine."""
import voluptuous as vol

ATTR_URL = 'url'
ATTR_URL_DEFAULT = 'https://www.google.com'

DOMAIN = 'browser'

SERVICE_BROWSE_URL = 'browse_url'

SERVICE_BROWSE_URL_SCHEMA = vol.Schema({
    # pylint: disable=no-value-for-parameter
    vol.Required(ATTR_URL, default=ATTR_URL_DEFAULT): vol.Url(),
})


def setup(hass, config):
    """Listen for browse_url events."""
    import webbrowser

    hass.services.register(DOMAIN, SERVICE_BROWSE_URL,
                           lambda service:
                           webbrowser.open(service.data[ATTR_URL]),
                           schema=SERVICE_BROWSE_URL_SCHEMA)

    return True
