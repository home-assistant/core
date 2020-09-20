"""Common classes and functions for Zoom."""
import json
from logging import getLogger
from typing import Dict, Optional

from aiohttp.web import HTTPException, Request, Response

from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import HTTP_OK
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.network import get_url

from .const import HA_URL, HA_ZOOM_EVENT, WEBHOOK_RESPONSE_SCHEMA

_LOGGER = getLogger(__name__)


def get_contact_name(contact: Optional[Dict[str, str]]) -> Optional[str]:
    """Determine contact name from available first name, last naame, and email."""
    if contact:
        contact_name = ""
        if contact.get("first_name"):
            contact_name = f"{contact['first_name']} "
        if contact.get("last_name"):
            contact_name += f"{contact['last_name']} "

        if contact_name:
            return f"{contact_name}({contact['email']})"
        return contact["email"]
    return None


class ZoomOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Oauth2 implementation that only uses the external url."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
        verification_token: Optional[str],
    ) -> None:
        """Initialize local auth implementation."""
        self.verification_token = verification_token
        super().__init__(
            hass, domain, client_id, client_secret, authorize_url, token_url
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return self._domain.title()

    @property
    def domain(self) -> str:
        """Domain of the implementation."""
        return self._domain

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        url = get_url(self.hass, allow_internal=False, prefer_cloud=True)
        return f"{url}{config_entry_oauth2_flow.AUTH_CALLBACK_PATH}"


class ZoomWebhookRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    requires_auth = False
    core_allowed = True
    url = HA_URL
    name = HA_URL[1:].replace("/", ":")

    def __init__(self, verification_token: Optional[str]) -> None:
        """Initialize view."""
        self._verification_token = verification_token

    async def post(self, request: Request) -> Response:
        """Respond to requests from the device."""
        hass = request.app["hass"]
        headers = request.headers

        if not (
            "authorization" in headers
            and (
                self._verification_token is None
                or headers["authorization"] == self._verification_token
            )
        ):
            _LOGGER.warning(
                "Received unauthorized request: %s (Headers: %s)",
                await request.text(),
                json.dumps(request.headers),
            )
        else:
            try:
                data = await request.json()
                status = WEBHOOK_RESPONSE_SCHEMA(data)
                _LOGGER.debug("Received event: %s", json.dumps(status))
                hass.bus.async_fire(HA_ZOOM_EVENT, status)
            except HTTPException:
                _LOGGER.warning(
                    "Received authorized but unknown event: %s", await request.text()
                )

        return Response(status=HTTP_OK)
