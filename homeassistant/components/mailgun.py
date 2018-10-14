"""
Support for Mailgun.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mailgun/
"""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY, CONF_DOMAIN
from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView


DOMAIN = 'mailgun'
API_PATH = '/api/{}'.format(DOMAIN)
DATA_MAILGUN = DOMAIN
DEPENDENCIES = ['http']
MESSAGE_RECEIVED = '{}_message_received'.format(DOMAIN)
CONF_SANDBOX = 'sandbox'
DEFAULT_SANDBOX = False

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Optional(CONF_SANDBOX, default=DEFAULT_SANDBOX): cv.boolean
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Mailgun component."""
    hass.data[DATA_MAILGUN] = config[DOMAIN]
    hass.http.register_view(MailgunReceiveMessageView())
    return True


class MailgunReceiveMessageView(HomeAssistantView):
    """Handle data from Mailgun inbound messages."""

    url = API_PATH
    name = 'api:{}'.format(DOMAIN)

    @callback
    def post(self, request):  # pylint: disable=no-self-use
        """Handle Mailgun message POST."""
        hass = request.app['hass']
        data = yield from request.post()
        hass.bus.async_fire(MESSAGE_RECEIVED, dict(data))
