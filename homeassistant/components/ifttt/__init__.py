"""
Support to trigger Maker IFTTT recipes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ifttt/
"""
from ipaddress import ip_address
import json
import logging
from urllib.parse import urlparse

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.util.network import is_local

REQUIREMENTS = ['pyfttt==0.3']
DEPENDENCIES = ['webhook']

_LOGGER = logging.getLogger(__name__)

EVENT_RECEIVED = 'ifttt_webhook_received'

ATTR_EVENT = 'event'
ATTR_VALUE1 = 'value1'
ATTR_VALUE2 = 'value2'
ATTR_VALUE3 = 'value3'

CONF_KEY = 'key'
CONF_WEBHOOK_ID = 'webhook_id'

DOMAIN = 'ifttt'

SERVICE_TRIGGER = 'trigger'

SERVICE_TRIGGER_SCHEMA = vol.Schema({
    vol.Required(ATTR_EVENT): cv.string,
    vol.Optional(ATTR_VALUE1): cv.string,
    vol.Optional(ATTR_VALUE2): cv.string,
    vol.Optional(ATTR_VALUE3): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Required(CONF_KEY): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the IFTTT service component."""
    if DOMAIN not in config:
        return True

    key = config[DOMAIN][CONF_KEY]

    def trigger_service(call):
        """Handle IFTTT trigger service calls."""
        event = call.data[ATTR_EVENT]
        value1 = call.data.get(ATTR_VALUE1)
        value2 = call.data.get(ATTR_VALUE2)
        value3 = call.data.get(ATTR_VALUE3)

        try:
            import pyfttt
            pyfttt.send_event(key, event, value1, value2, value3)
        except requests.exceptions.RequestException:
            _LOGGER.exception("Error communicating with IFTTT")

    hass.services.async_register(DOMAIN, SERVICE_TRIGGER, trigger_service,
                                 schema=SERVICE_TRIGGER_SCHEMA)

    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    body = await request.text()
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        return None

    if isinstance(data, dict):
        data['webhook_id'] = webhook_id
    hass.bus.async_fire(EVENT_RECEIVED, data)


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        entry.data['webhook_id'], handle_webhook)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data['webhook_id'])
    return True


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow):
    """Handle an IFTTT config flow."""

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
            title='IFTTT Webhook',
            data={
                CONF_WEBHOOK_ID: webhook_id
            },
            description_placeholders={
                'applet_url': 'https://ifttt.com/maker_webhooks',
                'webhook_url': webhook_url,
                'docs_url':
                'https://www.home-assistant.io/components/ifttt/'
            }
        )
