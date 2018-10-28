"""
Support for Mailgun.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mailgun/
"""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY, CONF_DOMAIN, CONF_WEBHOOK_ID
from homeassistant.helpers import config_entry_flow

DOMAIN = 'mailgun'
API_PATH = '/api/{}'.format(DOMAIN)
DEPENDENCIES = ['webhook']
MESSAGE_RECEIVED = '{}_message_received'.format(DOMAIN)
CONF_SANDBOX = 'sandbox'
DEFAULT_SANDBOX = False

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Optional(CONF_SANDBOX, default=DEFAULT_SANDBOX): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Mailgun component."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = config[DOMAIN]
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook with Mailgun inbound messages."""
    data = dict(await request.post())
    data['webhook_id'] = webhook_id
    hass.bus.async_fire(MESSAGE_RECEIVED, data)


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        entry.data[CONF_WEBHOOK_ID], handle_webhook)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])
    return True

config_entry_flow.register_webhook_flow(
    DOMAIN,
    'Mailgun Webhook',
    {
        'mailgun_url':
            'https://www.mailgun.com/blog/a-guide-to-using-mailguns-webhooks',
        'docs_url': 'https://www.home-assistant.io/components/mailgun/'
    }
)
