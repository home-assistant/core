"""
Support for Mailgun.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mailgun/
"""
import hashlib
import hmac
import json
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY, CONF_DOMAIN, CONF_WEBHOOK_ID
from homeassistant.helpers import config_entry_flow

DOMAIN = 'mailgun'
_LOGGER = logging.getLogger(__name__)
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
    body = await request.text()
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        return None

    if isinstance(data, dict) and 'signature' in data.keys():
        if await verify_webhook(hass, **data['signature']):
            data['webhook_id'] = webhook_id
            hass.bus.async_fire(MESSAGE_RECEIVED, data)
            return

    _LOGGER.warning(
        'Mailgun webhook received an unauthenticated message - webhook_id: %s',
        webhook_id
    )


async def verify_webhook(hass, token=None, timestamp=None, signature=None):
    """Verify webhook was signed by Mailgun."""
    if DOMAIN not in hass.data:
        _LOGGER.warning('Cannot validate Mailgun webhook, missing API Key')
        return True

    if not (token and timestamp and signature):
        return False

    hmac_digest = hmac.new(
        key=bytes(hass.data[DOMAIN][CONF_API_KEY], 'utf-8'),
        msg=bytes('{}{}'.format(timestamp, token), 'utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, hmac_digest)


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
        'mailgun_url': 'https://documentation.mailgun.com/en/latest/user_manual.html#webhooks',  # noqa: E501 pylint: disable=line-too-long
        'docs_url': 'https://www.home-assistant.io/components/mailgun/'
    }
)
