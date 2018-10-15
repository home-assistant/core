"""
Support for Mailgun.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mailgun/
"""
from urllib.parse import urlparse

import voluptuous as vol
from ipaddress import ip_address

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_DOMAIN, CONF_WEBHOOK_ID
from homeassistant.util.network import is_local

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
        vol.Optional(CONF_WEBHOOK_ID): cv.string,
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
    data = await request.post()

    if isinstance(data, dict):
        data[CONF_WEBHOOK_ID] = webhook_id
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


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow):
    """Handle a Mailgun config flow."""

    async def async_step_user(self, user_input=None):
        """Handle a user initiated set up flow."""
        if self._async_current_entries():
            return self.async_abort(reason='one_instance_allowed')

        try:
            url_parts = urlparse(self.hass.config.api.base_url)

            if is_local(ip_address(url_parts.hostname)):
                return self.async_abort(reason='not_internet_accessible')
        except ValueError:
            # If it's not an IP address, it's very likely publicly accessible
            pass

        if user_input is None:
            return self.async_show_form(
                step_id='user',
            )

        webhook_id = self.hass.components.webhook.async_generate_id()
        webhook_url = \
            self.hass.components.webhook.async_generate_url(webhook_id)

        return self.async_create_entry(
            title='Mailgun Webhook',
            data={
                'webhook_id': webhook_id
            },
            description_placeholders={
                'mailgun_url':
                    'https://www.mailgun.com/blog/a-guide-to-using-mailguns-webhooks',  # pylint: disable=C0301
                'webhook_url': webhook_url,
                'docs_url':
                'https://www.home-assistant.io/components/mailgun/'
            }
        )
