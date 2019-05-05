"""Support for Leaf Spy."""
import logging

from aiohttp.web import Response
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http.view import HomeAssistantView


from .config_flow import CONF_SECRET, DOMAIN, URL_LEAFSPY_PATH

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize Leaf Spy component."""
    hass.data[DOMAIN] = {}
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data={}
        ))

    return True


async def async_setup_entry(hass, entry):
    """Set up Leaf Spy entry."""
    secret = entry.data[CONF_SECRET]

    context = LeafSpyContext(hass, secret)

    hass.data[DOMAIN]['context'] = context

    hass.http.register_view(LeafSpyView())

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            entry, 'device_tracker'))

    return True


class LeafSpyContext:
    """Hold the current Leaf Spy context."""

    def __init__(self, hass, secret):
        """Initialize a Leaf Spy context."""
        self.hass = hass
        self.secret = secret

    async def async_see(self, **data):
        """Send a see message to the device tracker."""
        raise NotImplementedError


class LeafSpyView(HomeAssistantView):
    """Handle incoming Leaf Spy requests."""

    url = URL_LEAFSPY_PATH
    name = "api:leafspy"
    requires_auth = False

    async def get(self, request):
        """Handle leafspy call."""
        hass = request.app['hass']
        context = hass.data[DOMAIN]['context']

        try:
            message = request.query

            if message['pass'] != context.secret:
                raise Exception("Invalid password")

            hass.helpers.dispatcher.async_dispatcher_send(
                DOMAIN, hass, context, message)

            return Response(status=200, text="\"status\":\"0\"")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error processing leafspy webhook")
            return Response(status=200, text="")
