"""
Support to trigger Maker IFTTT recipes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ifttt/
"""
import json
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.helpers import config_entry_flow

REQUIREMENTS = ['pyfttt==0.3']
DEPENDENCIES = ['webhook']

_LOGGER = logging.getLogger(__name__)

EVENT_RECEIVED = 'ifttt_webhook_received'

ATTR_EVENT = 'event'
ATTR_VALUE1 = 'value1'
ATTR_VALUE2 = 'value2'
ATTR_VALUE3 = 'value3'

CONF_KEY = 'key'

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
        entry.data[CONF_WEBHOOK_ID], handle_webhook)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])
    return True

config_entry_flow.register_webhook_flow(
    DOMAIN,
    'IFTTT Webhook',
    {
        'applet_url': 'https://ifttt.com/maker_webhooks',
        'docs_url': 'https://www.home-assistant.io/components/ifttt/'
    }
)
