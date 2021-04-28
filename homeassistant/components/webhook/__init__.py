"""Webhooks for Home Assistant."""
import logging
import secrets

from aiohttp.web import Request, Response
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import HTTP_OK
from homeassistant.core import callback
from homeassistant.helpers.network import get_url
from homeassistant.loader import bind_hass
from homeassistant.util.aiohttp import MockRequest

_LOGGER = logging.getLogger(__name__)

DOMAIN = "webhook"

URL_WEBHOOK_PATH = "/api/webhook/{webhook_id}"

WS_TYPE_LIST = "webhook/list"

SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_LIST}
)


@callback
@bind_hass
def async_register(hass, domain, name, webhook_id, handler):
    """Register a webhook."""
    handlers = hass.data.setdefault(DOMAIN, {})

    if webhook_id in handlers:
        raise ValueError("Handler is already defined!")

    handlers[webhook_id] = {"domain": domain, "name": name, "handler": handler}


@callback
@bind_hass
def async_unregister(hass, webhook_id):
    """Remove a webhook."""
    handlers = hass.data.setdefault(DOMAIN, {})
    handlers.pop(webhook_id, None)


@callback
def async_generate_id():
    """Generate a webhook_id."""
    return secrets.token_hex(32)


@callback
@bind_hass
def async_generate_url(hass, webhook_id):
    """Generate the full URL for a webhook_id."""
    # TODO check if this is needed
    # "ais-dom gate_id fix"
    # from homeassistant.components.ais_dom import ais_global
    #
    # gate_id = ais_global.get_sercure_android_id_dom()
    # return "{}{}".format(
    #     "https://" + gate_id + ".paczka.pro", async_generate_path(webhook_id)
    return "{}{}".format(
        get_url(hass, prefer_external=True, allow_cloud=False),
        async_generate_path(webhook_id),
    )


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
    if webhook is None and webhook_id != "aisdomprocesscommandfromframe":
        if isinstance(request, MockRequest):
            received_from = request.mock_source
        else:
            received_from = request.remote

        _LOGGER.warning(
            "Received message for unregistered webhook %s from %s",
            webhook_id,
            received_from,
        )
        # Look at content to provide some context for received webhook
        # Limit to 64 chars to avoid flooding the log
        content = await request.content.read(64)
        _LOGGER.debug("%s", content)
        return Response(status=HTTP_OK)

    try:
        # ais
        response = None
        if webhook_id == "aisdomprocesscommandfromframe":
            # TODO check the ais_ha_webhook_id
            # except ais/register_wear_os
            import homeassistant.components.ais_ai_service as ai

            try:
                rj = await request.json()
                if "ais_gate_client_id" in rj:
                    # new way with answer
                    response = await ai.async_process_json_from_frame(hass, rj)
                else:
                    # TODO remove this old way
                    await hass.services.async_call(
                        "ais_ai_service", "process_command_from_frame", rj
                    )
            except Exception:
                response = None
        if response is None and webhook is not None:
            response = await webhook["handler"](hass, webhook_id, request)
        if response is None:
            response = Response(status=HTTP_OK)
        return response
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error processing webhook %s", webhook_id)
        return Response(status=HTTP_OK)


async def async_setup(hass, config):
    """Initialize the webhook component."""
    hass.http.register_view(WebhookView)
    hass.components.websocket_api.async_register_command(
        WS_TYPE_LIST, websocket_list, SCHEMA_WS_LIST
    )
    return True


class WebhookView(HomeAssistantView):
    """Handle incoming webhook requests."""

    url = URL_WEBHOOK_PATH
    name = "api:webhook"
    requires_auth = False
    cors_allowed = True

    async def _handle(self, request: Request, webhook_id):
        """Handle webhook call."""
        _LOGGER.debug("Handling webhook %s payload for %s", request.method, webhook_id)
        hass = request.app["hass"]
        return await async_handle_webhook(hass, webhook_id, request)

    head = _handle
    post = _handle
    put = _handle


@callback
def websocket_list(hass, connection, msg):
    """Return a list of webhooks."""
    handlers = hass.data.setdefault(DOMAIN, {})
    result = [
        {"webhook_id": webhook_id, "domain": info["domain"], "name": info["name"]}
        for webhook_id, info in handlers.items()
    ]

    connection.send_message(websocket_api.result_message(msg["id"], result))
