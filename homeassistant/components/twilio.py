"""
Support for Twilio.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/twilio/
"""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView

REQUIREMENTS = ['twilio==6.19.1']

DOMAIN = 'twilio'

API_PATH = '/api/{}'.format(DOMAIN)

CONF_ACCOUNT_SID = 'account_sid'
CONF_AUTH_TOKEN = 'auth_token'

DATA_TWILIO = DOMAIN
DEPENDENCIES = ['http']

RECEIVED_DATA = '{}_data_received'.format(DOMAIN)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ACCOUNT_SID): cv.string,
        vol.Required(CONF_AUTH_TOKEN): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Twilio component."""
    from twilio.rest import TwilioRestClient
    conf = config[DOMAIN]
    hass.data[DATA_TWILIO] = TwilioRestClient(
        conf.get(CONF_ACCOUNT_SID), conf.get(CONF_AUTH_TOKEN))
    hass.http.register_view(TwilioReceiveDataView())
    return True


class TwilioReceiveDataView(HomeAssistantView):
    """Handle data from Twilio inbound messages and calls."""

    url = API_PATH
    name = 'api:{}'.format(DOMAIN)

    @callback
    def post(self, request):  # pylint: disable=no-self-use
        """Handle Twilio data post."""
        from twilio.twiml import TwiML
        hass = request.app['hass']
        data = yield from request.post()
        hass.bus.async_fire(RECEIVED_DATA, dict(data))
        return TwiML().to_xml()
