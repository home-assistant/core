"""Webhooks for Home Assistant."""
import logging

from aiohttp.web import Response
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.auth.util import generate_secret
from homeassistant.components import websocket_api
from homeassistant.components.http.view import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'webhook'

URL_WEBHOOK_PATH = "/api/webhook/{webhook_id}"

WS_TYPE_LIST = 'webhook/list'

SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_LIST,
})


@callback
@bind_hass
def async_register(hass, domain, name, webhook_id, handler):
    """Register a webhook."""
    handlers = hass.data.setdefault(DOMAIN, {})

    if webhook_id in handlers:
        raise ValueError('Handler is already defined!')

    handlers[webhook_id] = {
        'domain': domain,
        'name': name,
        'handler': handler
    }


@callback
@bind_hass
def async_unregister(hass, webhook_id):
    """Remove a webhook."""
    handlers = hass.data.setdefault(DOMAIN, {})
    handlers.pop(webhook_id, None)


@callback
def async_generate_id():
    """Generate a webhook_id."""
    return generate_secret(entropy=32)


@callback
@bind_hass
def async_generate_url(hass, webhook_id):
    """Generate the full URL for a webhook_id."""
    return "{}{}".format(hass.config.api.base_url,
                         async_generate_path(webhook_id))


@callback
def async_generate_path(webhook_id):
    """Generate the path component for a webhook_id."""
    return URL_WEBHOOK_PATH.format(webhook_id=webhook_id)


@bind_hass
async def async_handle_webhook(hass, webhook_id, request):
    """Handle a webhook."""
    handlers = hass.data.setdefault(DOMAIN, {})
    webhook = handlers.get(webhook_id)

    # Always respond successfully to not give away if a hook exists or not.
    if webhook is None:
        _LOGGER.warning(
            'Received message for unregistered webhook %s', webhook_id)
        return Response(status=200)

    try:
        response = await webhook['handler'](hass, webhook_id, request)
        if response is None:
            response = Response(status=200)
        return response
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error processing webhook %s", webhook_id)
        return Response(status=200)


async def async_setup(hass, config):
    """Initialize the webhook component."""
    hass.http.register_view(WebhookView)
    hass.components.websocket_api.async_register_command(
        WS_TYPE_LIST, websocket_list,
        SCHEMA_WS_LIST
    )
    return True


class WebhookView(HomeAssistantView):
    """Handle incoming webhook requests."""

    url = URL_WEBHOOK_PATH
    name = "api:webhook"
    requires_auth = False

    async def post(self, request, webhook_id):
        """Handle webhook call."""
        hass = request.app['hass']
        return await async_handle_webhook(hass, webhook_id, request)


@callback
def websocket_list(hass, connection, msg):
    """Return a list of webhooks."""
    handlers = hass.data.setdefault(DOMAIN, {})
    result = [{
        'webhook_id': webhook_id,
        'domain': info['domain'],
        'name': info['name'],
    } for webhook_id, info in handlers.items()]

    connection.send_message(
        websocket_api.result_message(msg['id'], result))
