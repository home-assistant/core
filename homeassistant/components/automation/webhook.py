"""
Offer webhook triggered automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/docs/automation/trigger/#webhook-trigger
"""
from functools import partial
import logging

from aiohttp import hdrs
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_PLATFORM, CONF_WEBHOOK_ID
import homeassistant.helpers.config_validation as cv

from . import DOMAIN as AUTOMATION_DOMAIN

DEPENDENCIES = ('webhook',)

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'webhook',
    vol.Required(CONF_WEBHOOK_ID): cv.string,
})


async def _handle_webhook(action, hass, webhook_id, request):
    """Handle incoming webhook."""
    result = {
        'platform': 'webhook',
        'webhook_id': webhook_id,
    }

    if 'json' in request.headers.get(hdrs.CONTENT_TYPE, ''):
        result['json'] = await request.json()
    else:
        result['data'] = await request.post()

    hass.async_run_job(action, {'trigger': result})


async def async_trigger(hass, config, action, automation_info):
    """Trigger based on incoming webhooks."""
    webhook_id = config.get(CONF_WEBHOOK_ID)
    hass.components.webhook.async_register(
        AUTOMATION_DOMAIN, automation_info['name'],
        webhook_id, partial(_handle_webhook, action))

    @callback
    def unregister():
        """Unregister webhook."""
        hass.components.webhook.async_unregister(webhook_id)

    return unregister
