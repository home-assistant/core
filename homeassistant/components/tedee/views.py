"""Views for Tedee integration, to be used for webhook from Tedee Bridge."""

from http import HTTPStatus
import logging

from aiohttp import web

from homeassistant.components.http.view import HomeAssistantView

from .coordinator import TedeeApiCoordinator

_LOGGER = logging.getLogger(__name__)


class TedeeWebhookView(HomeAssistantView):
    """Handle Tedee Webhook requests."""

    url = "/api/tedee/webhook"
    name = "api:tedee:webhook"

    requires_auth = True

    def __init__(self, coordinator: TedeeApiCoordinator) -> None:
        """Initialize the view."""
        self._coordinator = coordinator

    async def post(self, request: web.Request) -> web.Response:
        """Handle Tedee Webhook requests."""
        _LOGGER.debug("Tedee Webhook received")

        try:
            data = await request.json()
        except ValueError:
            _LOGGER.warning("Received invalid JSON from Tedee Bridge")
            return self.json_message("Invalid JSON specified.", HTTPStatus.BAD_REQUEST)

        _LOGGER.debug("Received JSON: %s", data)
        self._coordinator.webhook_received(data)

        return self.json_message("Message received")
