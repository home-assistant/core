"""Support for Twilio."""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.helpers import config_entry_flow

DOMAIN = 'twilio'

CONF_ACCOUNT_SID = 'account_sid'
CONF_AUTH_TOKEN = 'auth_token'

DATA_TWILIO = DOMAIN

RECEIVED_DATA = '{}_data_received'.format(DOMAIN)

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Required(CONF_ACCOUNT_SID): cv.string,
        vol.Required(CONF_AUTH_TOKEN): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Twilio component."""
    from twilio.rest import Client
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    hass.data[DATA_TWILIO] = Client(
        conf.get(CONF_ACCOUNT_SID), conf.get(CONF_AUTH_TOKEN))
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook from Twilio for inbound messages and calls."""
    from twilio.twiml import TwiML

    data = dict(await request.post())
    data['webhook_id'] = webhook_id
    hass.bus.async_fire(RECEIVED_DATA, dict(data))

    return TwiML().to_xml()


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        DOMAIN, 'Twilio', entry.data[CONF_WEBHOOK_ID], handle_webhook)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])
    return True


# pylint: disable=invalid-name
async_remove_entry = config_entry_flow.webhook_async_remove_entry


config_entry_flow.register_webhook_flow(
    DOMAIN,
    'Twilio Webhook',
    {
        'twilio_url':
            'https://www.twilio.com/docs/glossary/what-is-a-webhook',
        'docs_url': 'https://www.home-assistant.io/components/twilio/'
    }
)
