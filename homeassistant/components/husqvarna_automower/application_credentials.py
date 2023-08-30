"""Application credentials platform for Husqvarna Automower."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import HUSQVARNA_URL, OAUTH2_AUTHORIZE, OAUTH2_TOKEN


# pylint: disable=unused-argument
async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "oauth_creds_url": HUSQVARNA_URL,
        "redirect_uri": get_url(hass),
    }
